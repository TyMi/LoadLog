"""V0 über die Schussfolge: gleitender Mittelwert, Trend, ausgeschlossene Schüsse, Schnittstelle, PDF-Bericht."""

import re

import pytest
from fastapi.testclient import TestClient

from loadlog import charts, i18n, synth
from loadlog.api import create_app
from loadlog.db import Database


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.sqlite3"))


def test_moving_average_uses_the_last_n_values():
    assert charts.moving_average([1.0, 2.0, 3.0, 4.0, 10.0], 3) == [None, None, 2.0, 3.0, 17 / 3]
    assert charts.moving_average([5.0, 7.0], 3) == [None, None]
    assert charts.moving_average([], 3) == []


def _rec(excluded=(), n=6):
    db = Database(":memory:")
    spec = [{"number": 1, "shots": n, "v0": 300.0, "sd": 3.0, "weight_gr": 180.0}]
    sid = db.save_series(importer_series(spec))[0]
    for k in excluded:
        db.set_shot_excluded(sid, k, True)
    return db.get_series(sid)


def importer_series(specs):
    from loadlog import importer

    return importer.import_zip(synth.make_zip(seed=3, specs=specs)).series[0]


def test_sequence_chart_draws_points_average_and_trend():
    svg = charts.sequence_chart(_rec(), window=3, units="si", lang="de")
    assert svg.count("<circle") == 6 and svg.count("<polyline") == 1  # Mittelwertlinie
    assert "Gleitender Mittelwert (3 Schüsse)" in svg and "Trend" in svg and "je Schuss" in svg
    en = charts.sequence_chart(_rec(), window=3, units="imp", lang="en")
    assert "Moving average (3 shots)" in en and "per shot" in en and "fps" in en


def test_excluded_shots_are_open_circles_and_not_averaged():
    svg = charts.sequence_chart(_rec(excluded=[2, 4]), window=3)
    assert svg.count('fill="none" stroke="#8794a5"') == 2  # offene Kreise (ausgeschlossen)
    assert svg.count("<circle") == 6
    assert "(Ausgeschlossen)" in svg


def test_short_series_has_no_average_line():
    svg = charts.sequence_chart(_rec(n=2), window=3)
    assert "<polyline" not in svg and svg.count("<circle") == 2


def test_empty_series_gives_a_message():
    class R:
        shots: list = []

    assert i18n.t("de", "no_data") in charts.sequence_chart(R(), lang="de")


def test_endpoint_validates_and_renders(client):
    sid = client.post("/api/import", files={"file": ("s.zip", synth.make_zip(seed=5))}).json()["imported"][0]["id"]
    r = client.get(f"/api/charts/series/{sid}/sequence.svg?window=5&lang=en&units=imp&theme=light")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert "Moving average (5 shots)" in r.text
    assert client.get(f"/api/charts/series/{sid}/sequence.svg?window=1").json()["detail"]["code"] == "value_min"
    assert client.get(f"/api/charts/series/{sid}/sequence.svg?window=11").json()["detail"]["code"] == "value_max"
    assert client.get(f"/api/charts/series/{sid}/sequence.svg?lang=fr").status_code == 422
    assert client.get("/api/charts/series/9999/sequence.svg").status_code == 404


def test_series_report_contains_the_sequence_chart(client):
    sid = client.post("/api/import", files={"file": ("s.zip", synth.make_zip(seed=5))}).json()["imported"][0]["id"]
    html = client.get(f"/api/reports/series/{sid}?format=html&lang=en").text
    assert "V0 over the shot sequence" in html and len(re.findall(r"<svg", html)) >= 2
