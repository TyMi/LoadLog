import xml.etree.ElementTree as ET

import pytest

from loadlog import charts, i18n, stats, synth
from loadlog.db import Database
from loadlog.importer import import_zip


@pytest.fixture(scope="module")
def recs():
    db = Database(":memory:")
    ids = [db.save_series(s)[0] for s in import_zip(synth.make_zip(seed=4)).series]
    return [db.get_series(i, with_track=True) for i in ids]


def parse(svg):
    return ET.fromstring(svg)  # muss wohlgeformtes XML sein


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("units", ["si", "imp"])
def test_track_chart_valid_and_complete(recs, theme, units):
    rec = recs[0]
    rec.shots[1].excluded = True
    svg = charts.track_chart(rec, selected=3, units=units, theme=theme)
    root = parse(svg)
    ns = "{http://www.w3.org/2000/svg}"
    assert len(root.findall(f"{ns}polyline")) == len(rec.shots)
    assert ("fps" in svg) == (units == "imp") and ("m/s" in svg) == (units == "si")
    assert "stroke-dasharray=\"5 4\"" in svg  # ausgeschlossener Schuss gestrichelt
    rec.shots[1].excluded = False


def test_track_chart_german_decimal_comma(recs):
    assert "," in charts.track_chart(recs[0], lang="de") and "Distanz" in charts.track_chart(recs[0], lang="de")
    assert "Distance" in charts.track_chart(recs[0], lang="en")


def test_strip_chart_with_trend(recs):
    cols = [(f"S{r.number}", r, stats.compute(r.shots)) for r in recs]
    svg = charts.strip_chart(cols, trend=True, lang="en")
    parse(svg)
    assert "Trend" in svg and "per series" in svg
    assert "Trend" not in charts.strip_chart(cols, trend=False, lang="en")
    assert "Trend" not in charts.strip_chart(cols[:1], trend=True, lang="en")  # 1 Serie: kein Trend


def test_ladder_chart():
    pts = [{"x": 42.0 + i * 0.5, "avg": 280 + i * 4.0, "sd": 2.0, "n": 5, "label": f"S{i}"} for i in range(5)]
    svg = charts.ladder_chart(pts, xlabel="Menge (gr)")
    parse(svg)
    assert svg.count("<circle") == 5
    parse(charts.ladder_chart(pts[:1], xlabel="x"))  # ein Punkt
    assert "Keine Daten" in charts.ladder_chart([], xlabel="x")


def test_chart_escapes_markup():
    pts = [{"x": 1.0, "avg": 280.0, "sd": 1.0, "n": 1, "label": "<script>alert(1)</script>"}]
    svg = charts.ladder_chart(pts, xlabel="<b>x</b>")
    assert "<script>" not in svg and "<b>" not in svg
    parse(svg)


def test_ticks_are_nice():
    assert charts._ticks(0, 10)[0] == 0 and charts._ticks(0, 10)[-1] >= 10
    t = charts._ticks(271.3, 301.2)
    assert t[0] <= 271.3 and t[-1] >= 301.2


def test_i18n_keys_match():
    assert set(i18n.TEXTS["de"]) == set(i18n.TEXTS["en"])
    with pytest.raises(ValueError):
        i18n.check_lang("fr")


def _polylines(svg):
    ns = "{http://www.w3.org/2000/svg}"
    return {int(pl.get("data-shot")): pl for pl in parse(svg).findall(f"{ns}polyline")}


def test_track_chart_hover_data(recs):
    rec = recs[0]
    pls = _polylines(charts.track_chart(rec, lang="de", units="si"))
    assert set(pls) == {s.number for s in rec.shots}
    pl = pls[rec.shots[0].number]
    assert pl.get("data-label") == f"Schuss {rec.shots[0].number}"
    vals = pl.get("data-vals").split(";")
    assert len(vals) == len(pl.get("points").split())  # ein Wert je Punkt
    assert vals[0].endswith("m/s") and " m · " in vals[0]
    imp = _polylines(charts.track_chart(rec, lang="en", units="imp"))[rec.shots[0].number]
    assert "yd" in imp.get("data-vals") and "fps" in imp.get("data-vals")


def test_excluded_shot_is_grey_even_when_selected(recs):
    rec = recs[0]
    n = rec.shots[1].number
    rec.shots[1].excluded = True
    try:
        for sel in (None, n):
            pl = _polylines(charts.track_chart(rec, selected=sel, theme="dark"))[n]
            assert pl.get("stroke") == charts.PALETTES["dark"]["excl"]
            assert pl.get("stroke") != charts.PALETTES["dark"]["sel"]
            assert "Ausgeschlossen" in pl.get("data-label")
        assert float(_polylines(charts.track_chart(rec, selected=n))[n].get("stroke-width")) == 3
    finally:
        rec.shots[1].excluded = False


def test_strip_chart_thins_x_labels_for_many_series(recs):
    cols = [(f"Serie {i}", recs[0], stats.compute(recs[0].shots)) for i in range(1, 39)]
    svg = charts.strip_chart(cols, lang="de")
    parse(svg)
    labels = [t for t in svg.split("<text") if "Serie " in t.split("</text>")[0]]
    assert 0 < len(labels) <= 13 and "Serie 1<" in svg and "Serie 2<" not in svg
    few = charts.strip_chart(cols[:5], lang="de")
    assert all(f"Serie {i}<" in few for i in range(1, 6))  # wenige Serien: alle beschriftet
