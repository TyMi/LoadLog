import pytest

from loadlog import synth
from loadlog.csvio import CsvError, parse_report, parse_track, report_to_series, report_units
from loadlog.importer import ImportFailure, collect, import_dir, import_zip
from loadlog.lbr import LbrError, parse_lbr
from loadlog.models import DeviceUnits


@pytest.fixture(scope="module")
def card():
    return synth.make_sd_card(seed=7)


def test_lbr_roundtrip_matches_report(card):
    series = parse_lbr(card["LBR/SR0001/SR0001.lbr"])
    rep = parse_report(card["LBR/SR0001/SR0001 Report.csv"])
    assert series.number == 1 and len(series.shots) == 8
    for shot, row in zip(series.shots, rep.rows, strict=True):
        assert abs(shot.v0_ms - float(row["V0"])) < 0.51  # Report ist gerundet
        assert shot.signal_strength in {1, 2, 3, 4, 5}
        assert shot.taken_at.year == 2030
    assert series.device_avg_ms == pytest.approx(sum(s.v0_ms for s in series.shots) / 8, rel=1e-5)


def test_lbr_rejects_garbage():
    with pytest.raises(LbrError):
        parse_lbr(b"\x00" * 30)
    with pytest.raises(LbrError):
        parse_lbr(b"")


def test_report_with_nul_padding_and_dynamic_distances(card):
    rep = parse_report(card["LBR/SR0002/SR0002 Report.csv"])  # nul_pad
    assert rep.series_number == 2 and rep.device_id == "LBR-0000000"
    assert "V25" in rep.columns and len(rep.rows) == 10
    rep3 = parse_report(card["LBR/SR0003/SR0003 Report.csv"])  # Distanzen 5..23
    assert "V23" in rep3.columns and "V25" not in rep3.columns


def test_report_fallback_series_without_lbr(card):
    rep = parse_report(card["LBR/SR0003/SR0003 Report.csv"])
    s = report_to_series(rep)
    assert s.number == 3 and len(s.shots) == 5
    assert s.shots[0].distances_m == [5.0, 10.0, 15.0, 20.0, 23.0]
    assert s.shots[0].weight_g == pytest.approx(180 * 0.06479891, rel=1e-3)


def test_report_units_imperial_conversion():
    raw = (
        b"sep=;\r\nSeries No;0001;;\r\nUnits velocity;fps;;\r\nUnits distances;yd;;\r\n"
        b"Units kinetic energy;ft-lbf;;\r\nUnits weight;grain (gr);;\r\n\r\n"
        b"Shot ID;V0;V10;Ke0;Ke10;PF10;Proj. Weight;Date;Time;\r\n"
        b"0001;1000;990;400;392;178.20;180.00;01-02-2030;10:00:00;\r\n"
    )
    rep = parse_report(raw)
    u = report_units(rep)
    assert u == DeviceUnits("fps", "yd", "ft-lbf", "gr")
    s = report_to_series(rep)
    assert s.shots[0].v0_ms == pytest.approx(304.8)
    assert s.shots[0].distances_m == [pytest.approx(9.144)]


def test_track_parsing(card):
    t = parse_track(card["LBR/SR0001/TRK/Shot0001 Track.csv"])
    assert t.meta["Series No"] == "0001"
    assert t.points[0].snr is None and t.points[1].snr is not None
    assert t.points[-1].distance_m > 25
    assert all(b.distance_m > a.distance_m for a, b in zip(t.points, t.points[1:], strict=False))


def test_track_unit_conversion():
    raw = b"Time (s);Vel (fps);Dist (yd);SNR\r\n0.0;1000;0;-\r\n0.1;990;10;20\r\n"
    t = parse_track(raw)
    assert t.points[1].velocity_ms == pytest.approx(990 * 0.3048)
    assert t.points[1].distance_m == pytest.approx(9.144)


def test_track_bad_row():
    with pytest.raises(CsvError):
        parse_track(b"Time (s);Vel (m/s);Dist (m);SNR\r\nabc;1;2;3\r\n")


def test_import_zip_collects_series_with_tracks():
    res = import_zip(synth.make_zip(seed=3))
    assert [s.number for s in res.series] == [1, 2, 3]
    assert all(s.device_id == "LBR-0000000" for s in res.series)
    assert all(sh.track for s in res.series for sh in s.shots)


def test_import_dir(tmp_path):
    synth.write_sd_card(tmp_path, seed=2)
    assert len(import_dir(tmp_path).series) == 3


def test_import_rejects_non_labradar_zip(tmp_path):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "x")
    with pytest.raises(ImportFailure):
        import_zip(buf.getvalue())
    with pytest.raises(ImportFailure):
        import_zip(b"not a zip")
    with pytest.raises(ImportFailure):
        collect({})


def test_import_zip_ignores_path_traversal():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil/SR0001/SR0001.lbr", b"x")
    with pytest.raises(ImportFailure):
        import_zip(buf.getvalue())


def test_synth_is_deterministic():
    assert synth.make_sd_card(seed=5) == synth.make_sd_card(seed=5)
    assert synth.make_sd_card(seed=5) != synth.make_sd_card(seed=6)

