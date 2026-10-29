import pytest

from loadlog import synth
from loadlog.db import Database
from loadlog.grt import GrtError, looks_like_grt, parse_grtload


@pytest.fixture(scope="module")
def grt():
    return parse_grtload(synth.make_grtload())


def test_detects_format():
    assert looks_like_grt(synth.make_grtload())
    assert not looks_like_grt(synth.make_zip())


def test_header_maps_to_load(grt):
    ld = grt.load
    assert ld["bullet_maker"] == "Testhersteller" and ld["bullet_type"] == "Testgeschoss"
    assert ld["bullet_weight_gr"] == pytest.approx(180, abs=0.01)
    assert ld["powder_name"] == "TP-1" and ld["powder_lot"] == "P-7"
    assert ld["coal_mm"] == pytest.approx(71.5) and ld["seating_depth_mm"] == pytest.approx(10.5)
    assert ld["trial_type"] == "ladder" and "Lauflänge: 600 mm" in ld["notes"]
    assert ld["name"].startswith(".308 Win.")


def test_series_and_shots(grt):
    assert [s.number for s in grt.series] == [1, 2, 3, 1, 0]
    assert [s.charge_gr for s in grt.series] == pytest.approx([40.0, 40.5, 41.0, 41.5, 42.0], abs=0.01)
    s = grt.series[0]
    assert len(s.shots) == 5 and s.note == "Synthetisch"
    sh = s.shots[0]
    assert sh.taken_at.year == 2030 and sh.weight_g == pytest.approx(180 * 0.06479891)
    assert sh.distances_m == [5.0, 25.0, 50.0] and len(sh.velocities_ms) == 3
    assert sh.energy0_j == pytest.approx(0.5 * sh.weight_g / 1000 * sh.v0_ms**2)
    assert sh.mip == pytest.approx(0.1 * 180 * 0.06479891 * sh.v0_ms, rel=1e-6)  # Gewicht in Gramm
    assert len(sh.track) == 30 and sh.track[0].time_s == 0 and sh.track[1].time_s == pytest.approx(0.009)  # ms -> s
    assert sh.track[0].snr is None
    assert sh.v0_ms == pytest.approx(sh.track[0].velocity_ms)  # genauerer Track-Wert statt gerundetem V0


def test_series_without_track_keeps_v0_only(grt):
    last = grt.series[4]
    assert last.shots[0].track == [] and last.shots[0].v0_ms > 700


def test_duplicate_numbers_are_distinct_in_db(grt):
    db = Database(":memory:")
    results = [db.save_series(s) for s in grt.series]
    assert all(new for _, new in results) and len({sid for sid, _ in results}) == 5
    assert not any(new for _, new in [db.save_series(s) for s in grt.series])  # erneuter Import: alles bekannt
    rec = db.get_series(results[0][0], with_track=True)
    assert rec.charge_gr == pytest.approx(40.0, abs=0.01) and len(rec.shots[0].track) == 30


@pytest.mark.parametrize("bad", [
    b"<html/>",
    b"not xml",
    b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><GordonsReloadingTool/>',
    b"<GordonsReloadingTool><InnerBallistikInput/></GordonsReloadingTool>",
])
def test_rejects_bad_input(bad):
    with pytest.raises(GrtError):
        parse_grtload(bad)


def test_missing_weight_warns():
    data = synth.make_grtload().replace(b'name="mp"', b'name="xx"')
    res = parse_grtload(data)
    assert any("Geschossgewicht" in w for w in res.warnings) and res.series[0].shots[0].mip is None


def test_header_numbers_are_rounded(grt):
    assert grt.load["coal_mm"] == 71.5 and grt.load["seating_depth_mm"] == 10.5
    raw = synth.make_grtload().replace(b"71.5", b"72.44999999999999")
    assert parse_grtload(raw).load["coal_mm"] == 72.45


def test_series_names_from_grt(grt):
    # Standardnamen "Series N" bleiben leer (Anzeige "Serie N"), eigene Namen werden übernommen
    assert [s.name for s in grt.series] == [None, None, None, None, "Handnotiz"]
