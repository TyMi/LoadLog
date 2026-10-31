"""Status, Duplizieren und Varianten der Laborierung; Gruppengröße der Serie; Migration auf Schema 5."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from loadlog import synth
from loadlog.api import create_app
from loadlog.db import _SCHEMA, _SERIES_LOADS, SCHEMA_VERSION, Database


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.sqlite3"))


def _series(client) -> int:
    return client.post("/api/import", files={"file": ("s.zip", synth.make_zip(seed=5))}).json()["imported"][0]["id"]


def test_load_status_is_optional_and_validated(client):
    lid = client.post("/api/loads", json={"name": "A"}).json()["id"]
    assert client.get(f"/api/loads/{lid}").json()["status"] is None
    for status in ("draft", "testing", "validated", "retired"):
        assert client.put(f"/api/loads/{lid}", json={"status": status}).json()["status"] == status
    assert client.put(f"/api/loads/{lid}", json={"status": None}).json()["status"] is None
    assert client.put(f"/api/loads/{lid}", json={"status": "gut"}).status_code == 422


def test_duplicate_load_copies_master_data_without_series(client):
    sid = _series(client)
    lid = client.post("/api/loads", json={"name": "Original", "powder_name": "P", "charge_gr": 40.5, "status": "validated"}).json()["id"]
    client.put(f"/api/series/{sid}/loads/{lid}")
    r = client.post(f"/api/loads/{lid}/duplicate")
    assert r.status_code == 201
    copy = r.json()
    assert copy["name"] == "Original (Kopie)" and copy["status"] == "draft"
    assert copy["powder_name"] == "P" and copy["charge_gr"] == 40.5 and copy["parent_id"] == lid and copy["series_count"] == 0
    named = client.post(f"/api/loads/{lid}/duplicate", json={"name": "Variante B"}).json()
    assert named["name"] == "Variante B"
    detail = client.get(f"/api/loads/{lid}").json()
    assert detail["parent"] is None and [v["name"] for v in detail["variants"]] == ["Original (Kopie)", "Variante B"]
    child = client.get(f"/api/loads/{copy['id']}").json()
    assert child["parent"]["id"] == lid and child["parent"]["name"] == "Original"
    assert client.post("/api/loads/9999/duplicate").status_code == 404
    assert client.post(f"/api/loads/{lid}/duplicate", json={"name": "   "}).status_code == 422


def test_deleting_the_original_keeps_the_copy(client):
    lid = client.post("/api/loads", json={"name": "O"}).json()["id"]
    cid = client.post(f"/api/loads/{lid}/duplicate").json()["id"]
    assert client.delete(f"/api/loads/{lid}").status_code == 204
    assert client.get(f"/api/loads/{cid}").json()["parent"] is None  # Verweis entfällt, Kopie bleibt


def test_series_group_text(client):
    sid = _series(client)
    assert client.get(f"/api/series/{sid}").json()["group_text"] is None
    assert client.patch(f"/api/series/{sid}", json={"group_text": "  25 mm auf 100 m "}).json()["group_text"] == "25 mm auf 100 m"
    assert client.patch(f"/api/series/{sid}", json={"group_text": "x" * 201}).status_code == 422
    assert client.patch(f"/api/series/{sid}", json={"group_text": None}).json()["group_text"] is None


def _v4_schema() -> str:
    schema = _SCHEMA.replace(",\n  status TEXT, parent_id INTEGER REFERENCES loads(id) ON DELETE SET NULL", "")
    return schema.replace(",\n  group_text TEXT", "")


def test_migration_from_schema_4_adds_the_new_columns(tmp_path):
    path = tmp_path / "v4.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(_v4_schema() + _SERIES_LOADS)
    con.execute("PRAGMA user_version = 4")
    con.execute("INSERT INTO loads (name, trial_type, created_at) VALUES ('Alt','single','2030-01-01')")
    con.commit()
    con.close()
    db = Database(path)
    assert db.get_load(1)["status"] is None and db.get_load(1)["parent_id"] is None
    db.update_load(1, {"status": "testing"})
    assert db.get_load(1)["status"] == "testing"
    with db.conn() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert "group_text" in {r[1] for r in c.execute("PRAGMA table_info(series)")}


def test_restore_of_a_schema_4_backup_is_migrated(client, tmp_path):
    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(_v4_schema() + _SERIES_LOADS)
    con.execute("PRAGMA user_version = 4")
    con.execute("INSERT INTO loads (name, trial_type, created_at) VALUES ('Alt','single','2030-01-01')")
    con.commit()
    con.close()
    r = client.post("/api/system/restore", files={"file": ("b.sqlite3", path.read_bytes())}, headers={"X-LoadLog-Confirm": "restore"})
    assert r.status_code == 200 and r.json()["loads"] == 1
    assert client.get("/api/loads").json()[0]["status"] is None


def test_group_text_appears_in_the_series_report_escaped(client):
    sid = _series(client)
    client.patch(f"/api/series/{sid}", json={"group_text": "25 mm <b>auf</b> 100 m"})
    de = client.get(f"/api/reports/series/{sid}?lang=de&format=html").text
    en = client.get(f"/api/reports/series/{sid}?lang=en&format=html").text
    assert "Gruppengröße: 25 mm &lt;b&gt;auf&lt;/b&gt; 100 m" in de and "Group size:" in en and "<b>auf</b>" not in de
