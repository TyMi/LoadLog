import pytest

from loadlog import stats, synth
from loadlog.db import Database, NotFound
from loadlog.importer import import_zip


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def imported(db):
    res = import_zip(synth.make_zip(seed=11))
    return [db.save_series(s)[0] for s in res.series]


def test_save_series_is_idempotent(db):
    res = import_zip(synth.make_zip(seed=11))
    first = [db.save_series(s) for s in res.series]
    second = [db.save_series(s) for s in res.series]
    assert all(new for _, new in first) and not any(new for _, new in second)
    assert [i for i, _ in first] == [i for i, _ in second]


def test_series_roundtrip_with_track(db, imported):
    rec = db.get_series(imported[0], with_track=True)
    assert rec.number == 1 and len(rec.shots) == 8
    assert rec.shots[0].track and rec.shots[0].track[0].snr is None
    assert db.get_series(imported[0]).shots[0].track == []  # ohne Track nicht geladen
    assert rec.taken_at is not None and rec.taken_at.year == 2030


def test_exclude_shot_changes_stats(db, imported):
    before = stats.compute(db.get_series(imported[0]).shots)
    db.set_shot_excluded(imported[0], 1, True)
    rec = db.get_series(imported[0])
    after = stats.compute(rec.shots)
    assert before.n == 8 and after.n == 7 and rec.shots[0].excluded
    db.set_shot_excluded(imported[0], 1, False)
    assert stats.compute(db.get_series(imported[0]).shots).avg == pytest.approx(before.avg)
    with pytest.raises(NotFound):
        db.set_shot_excluded(imported[0], 99, True)


def test_load_crud_and_assignment(db, imported):
    w = db.create_weapon({"name": "Testwaffe", "caliber": ".308", "ignored": "x"})
    lid = db.create_load({"name": "Test", "trial_type": "ladder", "weapon_id": w, "charge_gr": 42.5})
    db.update_series(imported[0], {"load_ids": [lid], "charge_gr": 42.0, "note": "n"})
    assert db.list_series_ids(load_id=lid) == [imported[0]]
    assert imported[0] not in db.list_series_ids(unassigned=True)
    assert db.get_load(lid)["charge_gr"] == 42.5
    with pytest.raises(NotFound):
        db.update_series(imported[1], {"load_ids": [999]})
    db.delete_load(lid)  # Serien bleiben, Zuordnung wird gelöst
    assert db.get_series(imported[0]).load_id is None
    db.delete_weapon(w)
    with pytest.raises(NotFound):
        db.get_weapon(w)


def test_delete_series_cascades_shots(db, imported):
    db.delete_series(imported[0])
    with pytest.raises(NotFound):
        db.get_series(imported[0])
    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM shots WHERE series_id = ?", (imported[0],)).fetchone()[0] == 0


def test_sql_injection_in_values_is_inert(db):
    lid = db.create_load({"name": "x'); DROP TABLE loads;--"})
    assert db.get_load(lid)["name"].startswith("x'")
    assert len(db.list_loads()) == 1


def test_stats_values():
    from datetime import datetime

    from loadlog.models import Shot

    def shot(v, ex=False):
        return Shot(1, datetime(2030, 1, 1), 11.0, v, [], [], 100.0, [], None, 3, excluded=ex)

    st = stats.compute([shot(290.0), shot(300.0), shot(280.0), shot(400.0, ex=True)])
    assert st.n == 3 and st.avg == pytest.approx(290.0) and st.sd == pytest.approx(10.0)
    assert st.es == 20.0 and st.vmin == 280.0 and st.vmax == 300.0
    assert stats.compute([shot(1.0)]).sd is None
    assert stats.compute([]).avg is None


def test_linear_fit():
    slope, icpt = stats.linear_fit([0, 1, 2], [284.1, 288.7, 289.3])
    assert slope == pytest.approx(2.6) and icpt == pytest.approx(285.0 - 0.0, abs=1.0)
    assert stats.linear_fit([1], [1]) is None
    assert stats.linear_fit([1, 1], [1, 2]) is None


def test_mip_follows_sportordnung_formula(db, imported):
    shots = db.get_series(imported[0]).shots
    s0 = shots[0]
    # MIP = 0,1 × Geschossgewicht (g) × V0 (m/s)
    assert s0.mip == pytest.approx(0.1 * s0.weight_g * s0.v0_ms)
    st = stats.compute(shots)
    inc = [s.mip for s in shots if not s.excluded]
    assert st.mip_avg == pytest.approx(sum(inc) / len(inc)) and st.mip_min == pytest.approx(min(inc))
    s0.excluded = True
    try:
        assert stats.compute(shots).mip_min >= st.mip_min  # ausgeschlossen zählt nicht
    finally:
        s0.excluded = False


def test_mip_reference_value():
    from datetime import datetime

    from loadlog.models import Shot

    # Beispiel zur DSB-Sportordnung (Regel 2.21.1): 180 gr = 11,66 g bei 300 m/s -> 0,1 × 11,66 × 300 = 349,9 (Sportordnung: gerundet 350)
    s = Shot(1, datetime(2030, 1, 1), 180 * 0.06479891, 300.0, [], [], 1.0, [], None, None)
    assert s.mip == pytest.approx(349.9, abs=0.05) and round(s.mip) == 350
    assert Shot(1, datetime(2030, 1, 1), 11.66, 300.0, [], [], 1.0, [], None, None).mip == pytest.approx(349.8)


def test_mip_unknown_without_weight():
    from datetime import datetime

    from loadlog.models import Shot

    s = Shot(1, datetime(2030, 1, 1), 0.0, 300.0, [], [], 1.0, [], None, None)
    assert s.mip is None
    assert stats.compute([s]).mip_avg is None


def test_migrates_v1_database_adds_series_name(tmp_path, legacy_schema):
    import sqlite3

    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(legacy_schema().replace("number INTEGER NOT NULL, name TEXT, weight_override_g REAL,", "number INTEGER NOT NULL,"))
    con.execute("PRAGMA user_version = 1")
    con.execute("INSERT INTO series (number, device_id, source_key, imported_at) VALUES (1,'X','k','2030-01-01')")
    con.commit()
    con.close()
    db = Database(path)
    rec = db.get_series(1)
    assert rec.name is None and rec.number == 1 and rec.weight_override_g is None
    db.update_series(1, {"name": "Mein Name"})
    assert db.get_series(1).name == "Mein Name"
    assert Database(path).get_series(1).name == "Mein Name"  # zweites Öffnen migriert nicht erneut


def test_series_name_roundtrip(db, imported):
    db.update_series(imported[0], {"name": "Probe A"})
    assert db.get_series(imported[0]).name == "Probe A"
    db.update_series(imported[0], {"name": None})
    assert db.get_series(imported[0]).name is None


def test_weight_override_changes_mip_and_energy_but_not_raw_data(db, imported):
    sid = imported[0]
    base = db.get_series(sid)
    w0 = base.shots[0].weight_g
    db.update_series(sid, {"weight_override_g": 11.66})
    rec = db.get_series(sid)
    s0, b0 = rec.shots[0], base.shots[0]
    assert rec.weight_override_g == 11.66 and rec.measured_weight_g == pytest.approx(w0)
    assert s0.weight_g == 11.66 and s0.mip == pytest.approx(0.1 * 11.66 * s0.v0_ms)
    assert s0.energy0_j == pytest.approx(0.5 * 0.01166 * s0.v0_ms**2)
    assert len(s0.energies_j) == len(b0.energies_j) and s0.v0_ms == b0.v0_ms  # Geschwindigkeiten unverändert
    assert stats.compute(rec.shots).mip_avg == pytest.approx(sum(s.mip for s in rec.shots) / len(rec.shots))
    db.update_series(sid, {"weight_override_g": None})
    back = db.get_series(sid)
    assert back.weight_override_g is None and back.shots[0].weight_g == pytest.approx(w0)  # Messwert wieder da
    assert back.shots[0].energy0_j == pytest.approx(b0.energy0_j)
