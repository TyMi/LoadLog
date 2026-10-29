import pytest

from loadlog import report, synth
from loadlog.db import Database
from loadlog.importer import import_zip


@pytest.fixture(scope="module")
def recs():
    db = Database(":memory:")
    ids = [db.save_series(s)[0] for s in import_zip(synth.make_zip(seed=9)).series]
    out = [db.get_series(i, with_track=True) for i in ids]
    for r, (c, sd) in zip(out, [(42.0, 2.0), (42.5, 2.1), (43.0, 2.2)], strict=True):
        r.charge_gr, r.seating_depth_mm = c, sd
    return out


LOAD = {"name": "Test <b>Load</b>", "trial_type": "ladder", "powder_maker": "Hersteller", "powder_name": "Pulver X",
        "charge_gr": 42.0, "bullet_weight_gr": 180.0, "seating_depth_mm": 2.0, "seating_ref": "Ogive",
        "temperature_c": 15.0, "notes": "<script>x</script>", "case_firings": 2}


@pytest.mark.parametrize("lang,needle", [("de", "Serienbericht"), ("en", "Series report")])
def test_series_report_languages(recs, lang, needle):
    html = report.series_report(recs[0], LOAD, {"name": "Waffe", "caliber": ".308"}, lang=lang)
    assert needle in html and "<svg" in html and f'lang="{lang}"' in html


def test_report_escapes_user_text(recs):
    html = report.series_report(recs[0], LOAD, None)
    assert "<script>x" not in html and "&lt;script&gt;" in html and "&lt;b&gt;Load" in html


def test_report_marks_excluded_shots(recs):
    recs[0].shots[0].excluded = True
    html = report.series_report(recs[0], None)
    recs[0].shots[0].excluded = False
    assert 'class="ex"' in html and "Ausgeschlossen" in html


def test_compare_report_has_trend_and_ladder(recs):
    html = report.compare_report(recs, lang="en", load=LOAD)
    assert "Trend" in html and "V0 over Charge" in html and "V0 over Seating depth" in html
    assert report.compare_report(recs[:1], lang="de").count("<svg") == 1  # keine Leiter bei 1 Serie


def test_imperial_units_in_report(recs):
    assert "fps" in report.series_report(recs[0], None, units="imp") and "ft-lbf" in report.series_report(recs[0], None, units="imp")


@pytest.mark.skipif(not report.pdf_available(), reason="WeasyPrint/Pango nicht verfügbar")
def test_pdf_is_generated(recs):
    pdf = report.html_to_pdf(report.compare_report(recs, load=LOAD))
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000


def test_every_report_carries_the_disclaimer(tmp_path):
    from fastapi.testclient import TestClient

    from loadlog import synth
    from loadlog.api import create_app

    c = TestClient(create_app(db_path=tmp_path / "t.sqlite3"))
    r = c.post("/api/import", files={"file": ("c.zip", synth.make_zip(seed=5))}).json()
    sid = r["imported"][0]["id"]
    lid = c.post("/api/loads", json={"name": "Probe"}).json()["id"]
    c.put(f"/api/series/{sid}/loads/{lid}")
    for path in (f"/api/reports/series/{sid}", f"/api/reports/load/{lid}", f"/api/reports/compare?ids={sid}"):
        sep = "&" if "?" in path else "?"
        de = c.get(f"{path}{sep}format=html").text
        en = c.get(f"{path}{sep}format=html&lang=en").text
        assert "keine Ladeempfehlung" in de and "Verantwortung liegt beim Wiederlader" in de, path
        assert "not a load recommendation" in en and "the reloader is responsible" in en, path
