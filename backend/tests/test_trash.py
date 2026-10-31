"""Papierkorb: Löschen verschiebt, Wiederherstellen stellt Zuordnungen wieder her, endgültiges Löschen und Wiederimport."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from loadlog import synth
from loadlog.api import create_app
from loadlog.db import _SCHEMA, _SERIES_LOADS, Database

CONFIRM = {"X-LoadLog-Confirm": "restore"}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.sqlite3"))


def _setup(client):
    zip_bytes = synth.make_zip(seed=5)
    ids = [i["id"] for i in client.post("/api/import", files={"file": ("s.zip", zip_bytes)}).json()["imported"]]
    lid = client.post("/api/loads", json={"name": "Ladung"}).json()["id"]
    client.put(f"/api/series/{ids[0]}/loads/{lid}")
    client.put(f"/api/series/{ids[1]}/loads/{lid}")
    return zip_bytes, ids, lid


def test_deleted_series_disappears_everywhere_and_can_be_restored(client):
    _, ids, lid = _setup(client)
    n = len(client.get("/api/series").json())
    assert client.delete(f"/api/series/{ids[0]}").status_code == 204
    assert client.get(f"/api/series/{ids[0]}").status_code == 404
    assert len(client.get("/api/series").json()) == n - 1
    assert [s["id"] for s in client.get(f"/api/loads/{lid}").json()["series"]] == [ids[1]]
    assert client.get(f"/api/loads/{lid}").json()["series_count"] == 1
    assert client.patch(f"/api/series/{ids[0]}", json={"name": "x"}).status_code == 404
    assert client.put(f"/api/series/{ids[0]}/shots/1/excluded", json={"excluded": True}).status_code == 404
    assert client.get(f"/api/compare?ids={ids[0]},{ids[1]}").status_code == 404
    assert client.delete(f"/api/series/{ids[0]}").status_code == 404  # nicht zweimal

    trash = client.get("/api/trash").json()
    assert [s["id"] for s in trash["series"]] == [ids[0]] and trash["series"][0]["shots_total"] > 0 and trash["loads"] == []

    assert client.post(f"/api/trash/series/{ids[0]}/restore").status_code == 200
    assert client.get("/api/trash").json() == {"series": [], "loads": []}
    assert len(client.get("/api/series").json()) == n
    assert sorted(client.get(f"/api/series/{ids[0]}").json()["load_ids"]) == [lid]  # Zuordnung bleibt
    assert client.post(f"/api/trash/series/{ids[0]}/restore").status_code == 404  # nicht im Papierkorb


def test_deleted_load_hides_its_series_assignment_and_comes_back(client):
    _, ids, lid = _setup(client)
    assert client.delete(f"/api/loads/{lid}").status_code == 204
    assert client.get(f"/api/loads/{lid}").status_code == 404
    assert client.get("/api/loads").json() == []
    assert client.get(f"/api/series/{ids[0]}").json()["load_ids"] == []  # gilt als nicht zugeordnet
    unassigned = [s["id"] for s in client.get("/api/series?unassigned=true").json()]
    assert ids[0] in unassigned and ids[1] in unassigned
    assert client.put(f"/api/series/{ids[2]}/loads/{lid}").status_code == 404
    assert client.post(f"/api/import?load_id={lid}", files={"file": ("s.zip", synth.make_zip(seed=5))}).status_code == 404
    trash = client.get("/api/trash").json()
    assert [x["id"] for x in trash["loads"]] == [lid] and trash["loads"][0]["series_count"] == 2

    assert client.post(f"/api/trash/loads/{lid}/restore").status_code == 200
    assert client.get(f"/api/series/{ids[0]}").json()["load_ids"] == [lid]
    assert len(client.get(f"/api/loads/{lid}").json()["series"]) == 2


def test_purge_one_or_all(client):
    _, ids, lid = _setup(client)
    client.delete(f"/api/series/{ids[0]}")
    client.delete(f"/api/series/{ids[1]}")
    client.delete(f"/api/loads/{lid}")
    assert client.delete(f"/api/trash/series/{ids[0]}").json() == {"series": 1, "loads": 0}
    assert client.delete(f"/api/trash/series/{ids[2]}").status_code == 404  # nicht im Papierkorb
    assert client.delete(f"/api/trash/series/{ids[0]}").status_code == 404
    assert client.post(f"/api/trash/series/{ids[0]}/restore").status_code == 404
    assert client.delete("/api/trash").json() == {"series": 1, "loads": 1}
    assert client.get("/api/trash").json() == {"series": [], "loads": []}
    assert client.get(f"/api/series/{ids[2]}").status_code == 200  # alles andere unberührt


def test_trash_routes_validate_the_kind(client):
    assert client.post("/api/trash/shots/1/restore").status_code == 422
    assert client.delete("/api/trash/weapons/1").status_code == 422


def test_reimport_after_delete_replaces_the_trashed_copy(client):
    zip_bytes, ids, _ = _setup(client)
    client.delete(f"/api/series/{ids[0]}")
    r = client.post("/api/import", files={"file": ("s.zip", zip_bytes)}).json()
    assert [i["number"] for i in r["imported"]] != [] and r["skipped"] == len(ids) - 1
    assert client.get("/api/trash").json()["series"] == []  # die Kopie im Papierkorb ist ersetzt
    new_id = r["imported"][0]["id"]
    assert client.get(f"/api/series/{new_id}").status_code == 200


def test_trashed_series_does_not_count_as_duplicate_for_other_sources(client):
    grt = synth.make_grtload()
    first = client.post("/api/import", files={"file": ("x.grtload", grt)}).json()
    for item in first["imported"]:
        client.delete(f"/api/series/{item['id']}")
    again = client.post("/api/import", files={"file": ("x.grtload", grt)}).json()
    assert len(again["imported"]) == len(first["imported"]) and again["skipped"] == 0


def test_backups_keep_the_trash_and_old_databases_migrate(client, tmp_path):
    _, ids, _ = _setup(client)
    client.delete(f"/api/series/{ids[0]}")
    backup = client.get("/api/system/backup").content
    other = TestClient(create_app(db_path=tmp_path / "o.sqlite3"))
    assert other.post("/api/system/restore", files={"file": ("b.sqlite3", backup)}, headers=CONFIRM).status_code == 200
    assert [s["id"] for s in other.get("/api/trash").json()["series"]] == [ids[0]]

    old = tmp_path / "v5.sqlite3"  # Schema 5: ohne deleted_at
    con = sqlite3.connect(old)
    con.executescript(_SCHEMA.replace(",\n  deleted_at TEXT", "").replace(", deleted_at TEXT", "") + _SERIES_LOADS)
    con.execute("PRAGMA user_version = 5")
    con.execute("INSERT INTO loads (name, trial_type, created_at) VALUES ('Alt','single','2030-01-01')")
    con.commit()
    con.close()
    db = Database(old)
    assert db.get_load(1)["name"] == "Alt" and db.list_trash() == {"series": [], "loads": []}
