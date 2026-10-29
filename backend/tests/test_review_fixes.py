"""Regressionstests zu den Befunden der unabhängigen Prüfung (Wiederherstellung, Importfehler, Schutz vor fremden Webseiten)."""

import io
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

from loadlog import importer, synth
from loadlog.api import create_app
from loadlog.db import Database


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.sqlite3"))


def seed(client):
    r = client.post("/api/import", files={"file": ("c.zip", synth.make_zip(seed=5))}).json()
    lid = client.post("/api/loads", json={"name": "Probe", "bullet_weight_gr": 180}).json()["id"]
    client.put(f"/api/series/{r['imported'][0]['id']}/loads/{lid}")
    return lid, r["imported"][0]["id"]


def restore(client, data):
    return client.post("/api/system/restore", files={"file": ("b.sqlite3", data)}, headers={"X-LoadLog-Confirm": "restore"})


# ---- Wiederherstellung (N1) ----
def test_restore_with_lower_version_label_does_not_break_the_instance(client, tmp_path):
    seed(client)
    f = tmp_path / "v3.sqlite3"
    f.write_bytes(client.get("/api/system/backup").content)
    con = sqlite3.connect(f)
    con.execute("PRAGMA user_version = 3")  # Version sagt 3, Inhalt ist schon Schema 4
    con.commit()
    con.close()
    assert restore(client, f.read_bytes()).status_code == 200
    assert client.post("/api/loads", json={"name": "danach"}).status_code == 201
    Database(tmp_path / "t.sqlite3")  # die App startet danach weiterhin


def test_restore_rejects_backup_with_missing_tables_and_keeps_data(client, tmp_path):
    seed(client)
    f = tmp_path / "x.sqlite3"
    f.write_bytes(client.get("/api/system/backup").content)
    con = sqlite3.connect(f)
    con.execute("DROP TABLE series_loads")
    con.commit()
    con.close()
    r = restore(client, f.read_bytes())
    assert r.status_code == 400 and r.json()["detail"]["code"] == "backup_invalid"
    assert len(client.get("/api/loads").json()) == 1 and client.get("/api/series").status_code == 200


def test_two_restores_in_the_same_second_keep_both_safety_copies(client, tmp_path):
    seed(client)
    backup = client.get("/api/system/backup").content
    assert restore(client, backup).status_code == 200 and restore(client, backup).status_code == 200
    assert len(list((tmp_path / "backups").glob("vor-wiederherstellung-*.sqlite3"))) == 2


# ---- Import (N7, N9) ----
def _zip(files: dict[str, bytes], method=zipfile.ZIP_STORED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", method) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_zip_entry_with_bad_checksum_is_skipped_not_a_server_error(client):
    files = synth.make_sd_card(seed=5)
    lbr = next(k for k in files if k.endswith(".lbr"))
    raw = bytearray(_zip(files))
    pos = bytes(raw).find(files[lbr][40:80])
    raw[pos + 10] ^= 0xFF  # ein Byte in den Daten der .lbr kippen: falsche CRC
    r = client.post("/api/import", files={"file": ("c.zip", bytes(raw))})
    assert r.status_code == 200
    assert any(w["code"] == "file_unreadable" for w in r.json()["warnings"])
    assert len(r.json()["imported"]) >= 1  # die übrigen Serien (und die betroffene über den Report) kommen an


def test_series_number_comes_from_the_folder_name():
    files = {k.replace("SR0001", "SR0300"): v for k, v in synth.make_sd_card(seed=5).items()}
    res = importer.import_zip(_zip(files))
    assert 300 in {s.number for s in res.series}
    assert any(getattr(w, "code", "") == "series_number_adjusted" for w in res.warnings)


# ---- Gewicht je Laborierung (N11) ----
def test_apply_weight_respects_the_same_limit_as_a_single_series(client):
    lid, sid = seed(client)
    client.put(f"/api/loads/{lid}", json={"bullet_weight_gr": 2000})  # 129,6 g liegt über der Grenze von 100 g
    r = client.post(f"/api/loads/{lid}/apply-weight")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "weight_out_of_range"
    assert client.get(f"/api/series/{sid}").json()["weight_override_g"] is None
    client.put(f"/api/loads/{lid}", json={"bullet_weight_gr": 150})
    assert client.post(f"/api/loads/{lid}/apply-weight").json()["series"] == 1


# ---- Schutz vor fremden Webseiten und Uploadgrenze (N6, N10) ----
def test_cross_site_writes_are_rejected_but_same_origin_and_reads_work(client):
    lid, sid = seed(client)
    for method, path in (("post", "/api/import"), ("post", f"/api/loads/{lid}/apply-weight"), ("post", "/api/system/restore"),
                         ("delete", f"/api/series/{sid}"), ("put", f"/api/series/{sid}/loads/{lid}")):
        for site in ("cross-site", "same-site"):
            r = getattr(client, method)(path, headers={"Sec-Fetch-Site": site})
            assert r.status_code == 403 and r.json()["detail"]["code"] == "cross_site_blocked", (method, path, site)
    assert client.get(f"/api/series/{sid}").status_code == 200  # nichts wurde gelöscht
    assert client.post("/api/loads", json={"name": "ok"}, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 201
    assert client.post("/api/loads", json={"name": "ohne Kopf"}).status_code == 201  # Skripte und Tests ohne Browser
    assert client.get("/api/loads", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


def test_upload_limit_is_checked_before_the_body_is_read(client, monkeypatch):
    monkeypatch.setattr("loadlog.api.MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
    r = client.post("/api/import", files={"file": ("c.zip", b"x" * (7 * 1024 * 1024))})
    assert r.status_code == 413 and r.json()["detail"]["code"] == "upload_too_large" and r.json()["detail"]["params"]["max"] == 5
    assert client.get("/api/series").json() == []


def test_allowed_hosts_setting_blocks_foreign_host_headers(tmp_path, monkeypatch):
    monkeypatch.setenv("LOADLOG_ALLOWED_HOSTS", "localhost, 127.0.0.1")
    c = TestClient(create_app(db_path=tmp_path / "t.sqlite3"))
    assert c.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert c.get("/api/health", headers={"Host": "localhost:8080"}).status_code == 200


def test_redoc_is_off_and_swagger_docs_stay(client):
    assert client.get("/redoc").status_code == 404
    assert client.get("/api/docs").status_code == 200
