"""Energie über Distanz: Profil aus gewerteten Schüssen, Diagramm, Schnittstelle, Bericht."""

import math

import pytest
from fastapi.testclient import TestClient

from loadlog import charts, i18n, importer, synth
from loadlog.api import create_app
from loadlog.db import Database


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "t.sqlite3"))


def _rec(exclude=()):
    db = Database(":memory:")
    spec = [{"number": 1, "shots": 5, "v0": 780.0, "sd": 3.0, "weight_gr": 180.0, "distances": (5, 10, 15, 20, 25)}]
    sid = db.save_series(importer.import_zip(synth.make_zip(seed=3, specs=spec)).series[0])[0]
    for n in exclude:
        db.set_shot_excluded(sid, n, True)
    return db.get_series(sid)


def test_profile_has_muzzle_and_each_distance_with_mean_and_sd():
    prof = charts.energy_profile(_rec().shots)
    assert [x["distance_m"] for x in prof] == [0.0, 5.0, 10.0, 15.0, 20.0, 25.0]
    assert all(x["n"] == 5 and x["sd_j"] is not None for x in prof)
    assert prof[0]["mean_j"] > prof[-1]["mean_j"]  # Energie nimmt mit der Distanz ab
    shots = _rec().shots
    expect = sum(s.energy0_j for s in shots) / len(shots)
    assert math.isclose(prof[0]["mean_j"], expect)


def test_excluded_shots_are_left_out():
    prof = charts.energy_profile(_rec(exclude=[1, 2]).shots)
    assert all(x["n"] == 3 for x in prof)
    assert charts.energy_profile(_rec(exclude=[1, 2, 3, 4, 5]).shots) == []


def test_single_shot_has_no_sd():
    prof = charts.energy_profile(_rec(exclude=[2, 3, 4, 5]).shots)
    assert all(x["n"] == 1 and x["sd_j"] is None for x in prof)


def test_chart_shows_values_in_the_chosen_units_and_language():
    de = charts.energy_chart(_rec(), units="si", lang="de")
    assert "Energie (J)" in de and "Distanz (m)" in de and de.count("<circle") == 6 and "<polygon" in de
    en = charts.energy_chart(_rec(), units="imp", lang="en")
    assert "Energy (ft-lbf)" in en and "Distance (yd)" in en
    muzzle_j = charts.energy_profile(_rec().shots)[0]["mean_j"]
    assert f"{muzzle_j * 0.7375621:.0f}" in en  # ft-lbf-Wert der Mündungsenergie als Beschriftung


def test_chart_without_enough_points_gives_a_message():
    series = importer.import_zip(synth.make_zip(seed=3)).series[0]
    series.shots = series.shots[:1]
    series.shots[0].distances_m, series.shots[0].energies_j = [], []
    db = Database(":memory:")
    sid = db.save_series(series)[0]
    assert i18n.t("de", "no_data") in charts.energy_chart(db.get_series(sid), lang="de")


def test_endpoint_and_report(client):
    sid = client.post("/api/import", files={"file": ("s.zip", synth.make_zip(seed=5))}).json()["imported"][0]["id"]
    r = client.get(f"/api/charts/series/{sid}/energy.svg?lang=en&units=imp")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and "Energy (ft-lbf)" in r.text
    assert client.get(f"/api/charts/series/{sid}/energy.svg?units=x").status_code == 422
    assert client.get("/api/charts/series/9999/energy.svg").status_code == 404
    html = client.get(f"/api/reports/series/{sid}?format=html&lang=de").text
    assert "Energie über Distanz" in html

