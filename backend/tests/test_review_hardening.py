"""Härtung aus der unabhängigen Prüfung vom 2026-10-31 (Origin, Cache-Control, Wiederherstellung, Einstellungen, GRT-Grenze)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from loadlog import synth
from loadlog.api import create_app, exposure_warning
from loadlog.grt import MAX_GRT_BYTES

CONFIRM = {"X-LoadLog-Confirm": "restore"}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "data" / "t.sqlite3"))


def _import(client):
    return client.post("/api/import", files={"file": ("s.zip", synth.make_zip(seed=5))}).json()["imported"][0]["id"]


# ---- SEC-04: Origin ----
def test_post_from_a_foreign_origin_is_blocked_even_without_fetch_metadata(client):
    r = client.post("/api/loads", json={"name": "X"}, headers={"Origin": "http://evil.example"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "cross_site_blocked"
    assert client.get("/api/loads").json() == []  # nichts angelegt


@pytest.mark.parametrize("origin", ["http://testserver", "https://testserver"])
def test_same_origin_posts_are_allowed(client, origin):
    assert client.post("/api/loads", json={"name": "X"}, headers={"Origin": origin}).status_code == 201


def test_origin_null_is_blocked_but_a_missing_origin_is_fine(client):
    assert client.post("/api/loads", json={"name": "X"}, headers={"Origin": "null"}).status_code == 403
    assert client.post("/api/loads", json={"name": "X"}).status_code == 201  # curl, Skripte, Tests


def test_origin_matching_a_proxy_host_or_allowed_host(tmp_path, monkeypatch):
    monkeypatch.setenv("LOADLOG_ALLOWED_HOSTS", "testserver,loadlog.lan")
    c = TestClient(create_app(db_path=tmp_path / "a.sqlite3"))
    assert c.post("/api/loads", json={"name": "A"}, headers={"Origin": "https://loadlog.lan"}).status_code == 201
    assert c.post("/api/loads", json={"name": "B"}, headers={"Origin": "http://evil.example"}).status_code == 403
    monkeypatch.delenv("LOADLOG_ALLOWED_HOSTS")
    c2 = TestClient(create_app(db_path=tmp_path / "b.sqlite3"))
    h = {"Origin": "https://loadlog.lan", "X-Forwarded-Host": "loadlog.lan"}
    assert c2.post("/api/loads", json={"name": "C"}, headers=h).status_code == 201


# ---- SEC-10: Cache-Control ----
def test_api_responses_are_not_cacheable(client):
    assert client.get("/api/loads").headers["cache-control"] == "no-store"
    assert client.get("/api/health").headers["cache-control"] == "no-store"


# ---- SEC-03: Warnung beim Start ----
@pytest.mark.parametrize("env,warns", [
    ({}, False),
    ({"LOADLOG_BIND": "127.0.0.1"}, False),
    ({"LOADLOG_HOST": "0.0.0.0"}, True),
    ({"LOADLOG_HOST": "0.0.0.0", "LOADLOG_BIND": "127.0.0.1"}, False),  # Container, Port nur lokal veröffentlicht
    ({"LOADLOG_BIND": "0.0.0.0"}, True),
    ({"LOADLOG_BIND": "0.0.0.0", "LOADLOG_ALLOWED_HOSTS": "loadlog.lan"}, False),
])
def test_exposure_warning(env, warns):
    assert (exposure_warning(env) is not None) is warns


# ---- SEC-02: Wiederherstellung ----
def _backup_file(client, tmp_path, tamper):
    _import(client)
    src = tmp_path / "good.sqlite3"
    src.write_bytes(client.get("/api/system/backup").content)
    con = sqlite3.connect(src)
    con.execute("PRAGMA foreign_keys = OFF")
    tamper(con)
    con.commit()
    con.close()
    return src


@pytest.mark.parametrize("name,tamper", [
    ("kaputtes JSON", lambda c: c.execute("UPDATE shots SET velocities_json = 'kein json' WHERE id = 1")),
    ("JSON ist keine Liste", lambda c: c.execute("UPDATE shots SET track_json = '{\"a\": 1}' WHERE id = 1")),
    ("Fremdschlüssel verletzt", lambda c: c.execute("UPDATE shots SET series_id = 9999 WHERE id = 1")),
])
def test_restore_rejects_inconsistent_data(client, tmp_path, name, tamper):
    src = _backup_file(client, tmp_path, tamper)
    before = client.get("/api/series").json()
    r = client.post("/api/system/restore", files={"file": ("b.sqlite3", src.read_bytes())}, headers=CONFIRM)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "backup_invalid", name
    assert client.get("/api/series").json() == before  # laufende Datenbank unberührt


def test_valid_backup_still_restores(client, tmp_path):
    src = _backup_file(client, tmp_path, lambda c: None)
    assert client.post("/api/system/restore", files={"file": ("b.sqlite3", src.read_bytes())}, headers=CONFIRM).status_code == 200


def test_restore_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("LOADLOG_ALLOW_RESTORE", "0")
    c = TestClient(create_app(db_path=tmp_path / "r.sqlite3"))
    r = c.post("/api/system/restore", files={"file": ("b.sqlite3", b"x")}, headers=CONFIRM)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "restore_disabled"
    assert c.get("/api/system/backup").status_code == 200  # Sicherung bleibt möglich


# ---- SEC-09: Sicherheitskopien und Einstellungen ----
def test_settings_default_and_validation(client):
    assert client.get("/api/settings").json() == {"backup_keep": 5}
    assert client.patch("/api/settings", json={"backup_keep": 0}).status_code == 422
    assert client.patch("/api/settings", json={"backup_keep": 101}).status_code == 422
    assert client.patch("/api/settings", json={"backup_keep": 2}).json() == {"backup_keep": 2}
    assert client.get("/api/settings").json() == {"backup_keep": 2}


def test_settings_survive_a_restart(tmp_path):
    path = tmp_path / "d" / "x.sqlite3"
    TestClient(create_app(db_path=path)).patch("/api/settings", json={"backup_keep": 7})
    assert TestClient(create_app(db_path=path)).get("/api/settings").json() == {"backup_keep": 7}
    (path.parent / "settings.json").write_text("kaputt")
    assert TestClient(create_app(db_path=path)).get("/api/settings").json() == {"backup_keep": 5}


def test_safety_copies_are_limited_to_the_configured_number(client, tmp_path):
    src = _backup_file(client, tmp_path, lambda c: None).read_bytes()
    client.patch("/api/settings", json={"backup_keep": 3})
    for _ in range(6):
        assert client.post("/api/system/restore", files={"file": ("b.sqlite3", src)}, headers=CONFIRM).status_code == 200
    folder = tmp_path / "data" / "backups"
    assert len(list(folder.glob("vor-wiederherstellung-*.sqlite3"))) == 3
    client.patch("/api/settings", json={"backup_keep": 1})  # kleinere Zahl räumt sofort auf
    assert len(list(folder.glob("vor-wiederherstellung-*.sqlite3"))) == 1


# ---- SEC-05: Grenze für GRT-Dateien ----
def test_grt_larger_than_10_mb_is_rejected(client):
    assert MAX_GRT_BYTES == 10 * 1024 * 1024
    big = b"<GordonsReloadingTool>" + b" " * (MAX_GRT_BYTES + 1)
    r = client.post("/api/import", files={"file": ("x.grtload", big)})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "grt_too_large"
