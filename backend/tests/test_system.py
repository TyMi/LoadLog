import json
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loadlog import __version__, synth
from loadlog.api import MANUAL_VERSION, create_app
from loadlog.db import SCHEMA_VERSION, Database

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.sqlite3"))


def seed(client):
    r = client.post("/api/import", files={"file": ("c.zip", synth.make_zip(seed=5))}).json()
    lid = client.post("/api/loads", json={"name": "Probe"}).json()["id"]
    sid = r["imported"][0]["id"]
    client.put(f"/api/series/{sid}/loads/{lid}")
    return lid, sid


# ---- Version ----
def test_version_is_three_part_and_consistent():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)
    pyproject = (ROOT / "backend" / "pyproject.toml").read_text()
    assert re.search(rf'^version = "{re.escape(__version__)}"$', pyproject, re.M)
    assert json.loads((ROOT / "frontend" / "package.json").read_text())["version"] == __version__
    assert MANUAL_VERSION == ".".join(__version__.split(".")[:2])


def test_health_reports_versions(client):
    h = client.get("/api/health").json()
    assert h["version"] == __version__ and h["manual_version"] == MANUAL_VERSION


def test_manual_is_served_under_major_minor_and_old_links_redirect(tmp_path):
    (tmp_path / "man" / "de").mkdir(parents=True)
    (tmp_path / "man" / "de" / "index.html").write_text("<h1>handbuch</h1>")
    c = TestClient(create_app(db_path=tmp_path / "t.sqlite3", manual_dir=tmp_path / "man"), follow_redirects=False)
    assert "handbuch" in c.get(f"/manual/{MANUAL_VERSION}/de/").text
    r = c.get("/manual/de/")
    assert r.status_code == 307 and r.headers["location"] == f"/manual/{MANUAL_VERSION}/de/"
    assert c.get("/manual/").headers["location"] == f"/manual/{MANUAL_VERSION}/"
    assert c.head("/manual/de/").status_code == 307
    assert c.get("/manual/xx/").headers["location"] == f"/manual/{MANUAL_VERSION}/"  # unbekannte Sprache: keine freie Weiterleitung


# ---- CSV-Export ----
def test_csv_export_series_de_and_en(client):
    lid, sid = seed(client)
    de = client.get(f"/api/export/series/{sid}.csv")
    assert de.status_code == 200 and de.headers["content-type"].startswith("text/csv")
    assert de.text.startswith("﻿") and "attachment" in de.headers["content-disposition"]
    lines = de.text.lstrip("﻿").split("\r\n")
    assert lines[0].startswith("Laborierung;Serie;") and lines[1].startswith("Probe;")
    assert len(lines) - 1 - 1 == client.get(f"/api/series/{sid}").json()["shots_total"]  # Kopf und leere Schlusszeile
    assert re.search(r";\d+,\d;", lines[1])  # Dezimalkomma
    en = client.get(f"/api/export/series/{sid}.csv?lang=en&units=imp").text.lstrip("﻿").split("\r\n")
    assert en[0].startswith("Load,Series,") and "fps" in en[0] and re.search(r",\d+\.\d,", en[1])


def test_csv_export_load_contains_all_series(client):
    lid, sid = seed(client)
    n = client.get(f"/api/series/{sid}").json()["shots_total"]
    text = client.get(f"/api/export/load/{lid}.csv").text
    assert len(text.strip().split("\r\n")) == n + 1
    assert client.get("/api/export/load/9999.csv").status_code == 404
    assert client.get(f"/api/export/series/{sid}.csv?lang=xx").status_code == 422


def test_csv_neutralises_formula_injection(client):
    lid, sid = seed(client)
    client.patch(f"/api/series/{sid}", json={"name": "=HYPERLINK(\"http://x\")"})
    row = client.get(f"/api/export/series/{sid}.csv").text.split("\r\n")[1]
    assert "'=HYPERLINK" in row and ";=HYPERLINK" not in row


# ---- Sicherung ----
def test_backup_download_is_a_valid_database(client, tmp_path):
    seed(client)
    r = client.get("/api/system/backup")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    f = tmp_path / "b.sqlite3"
    f.write_bytes(r.content)
    assert Database.check_backup(f) == SCHEMA_VERSION
    con = sqlite3.connect(f)
    assert con.execute("SELECT COUNT(*) FROM series_loads").fetchone()[0] == 1


def restore(client, data, confirm=True):
    return client.post("/api/system/restore", files={"file": ("b.sqlite3", data)},
                       headers={"X-LoadLog-Confirm": "restore"} if confirm else {})


def test_restore_replaces_everything_and_keeps_safety_copy(client, tmp_path):
    lid, sid = seed(client)
    backup = client.get("/api/system/backup").content
    client.delete(f"/api/series/{sid}")
    client.post("/api/loads", json={"name": "Nach der Sicherung"})
    r = restore(client, backup)
    assert r.status_code == 200 and r.json()["series"] >= 1 and r.json()["loads"] == 1
    assert [x["name"] for x in client.get("/api/loads").json()] == ["Probe"]
    assert client.get(f"/api/series/{sid}").status_code == 200
    saved = list((tmp_path / "backups").glob("vor-wiederherstellung-*.sqlite3"))
    assert len(saved) == 1  # Stand vor der Wiederherstellung
    con = sqlite3.connect(saved[0])
    assert sorted(x[0] for x in con.execute("SELECT name FROM loads")) == ["Nach der Sicherung", "Probe"]
    # die Datenbank bleibt danach voll nutzbar (Schreiben, WAL)
    assert client.post("/api/loads", json={"name": "Neu"}).status_code == 201
    assert Database(tmp_path / "t.sqlite3").list_loads()


def test_restore_needs_confirmation_header(client):
    seed(client)
    backup = client.get("/api/system/backup").content
    r = restore(client, backup, confirm=False)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "restore_confirm"
    assert len(client.get("/api/loads").json()) == 1


@pytest.mark.parametrize("data", [b"", b"kein sqlite", b"SQLite format 3\x00" + b"\x00" * 200])
def test_restore_rejects_garbage_and_keeps_data(client, data):
    seed(client)
    r = restore(client, data)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "backup_invalid"
    assert len(client.get("/api/loads").json()) == 1


def test_restore_rejects_foreign_database_and_triggers(client, tmp_path):
    seed(client)
    foreign = tmp_path / "f.sqlite3"
    con = sqlite3.connect(foreign)
    con.execute("CREATE TABLE x (a)")
    con.commit()
    con.close()
    assert restore(client, foreign.read_bytes()).json()["detail"]["code"] == "backup_invalid"
    good = tmp_path / "g.sqlite3"
    good.write_bytes(client.get("/api/system/backup").content)
    con = sqlite3.connect(good)
    con.execute("CREATE TRIGGER t AFTER INSERT ON loads BEGIN DELETE FROM series; END")
    con.commit()
    con.close()
    assert restore(client, good.read_bytes()).json()["detail"]["code"] == "backup_invalid"
    assert len(client.get("/api/loads").json()) == 1


def test_restore_rejects_newer_schema_and_upgrades_older(client, tmp_path, legacy_schema):
    newer = tmp_path / "n.sqlite3"
    newer.write_bytes(client.get("/api/system/backup").content)
    con = sqlite3.connect(newer)
    con.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    con.commit()
    con.close()
    r = restore(client, newer.read_bytes())
    assert r.status_code == 400 and r.json()["detail"]["code"] == "backup_too_new"
    old = tmp_path / "o.sqlite3"
    con = sqlite3.connect(old)
    con.executescript(legacy_schema())
    con.execute("PRAGMA user_version = 3")
    con.execute("INSERT INTO loads (name, trial_type, created_at) VALUES ('Alt','single','2030-01-01')")
    con.execute("INSERT INTO series (load_id, number, device_id, source_key, imported_at) VALUES (1,1,'X','k','2030-01-01')")
    con.commit()
    con.close()
    assert restore(client, old.read_bytes()).status_code == 200
    assert client.get("/api/series/1").json()["load_ids"] == [1]  # Schema 3 wurde angehoben
