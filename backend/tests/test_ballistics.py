from datetime import datetime

import pytest

from loadlog import ballistics as b
from loadlog.models import Shot, TrackPoint


def _shot(model: str, bc: float, v0: float = 800.0, span: float = 60.0, noise: float = 0.0, excluded: bool = False) -> Shot:
    xs = [i * 1.5 for i in range(1, int(span / 1.5) + 1)]
    vs = b._simulate(model, bc, 0.0, v0, xs)
    track = [TrackPoint(0.0, v0, 0.0, None)] + [
        TrackPoint(0.0, v + noise * (-1) ** i, x, 20.0) for i, (x, v) in enumerate(zip(xs, vs, strict=True))
    ]
    return Shot(1, datetime(2030, 1, 1), 10.0, v0, [], [], 3000.0, [], None, 4, track, excluded)


@pytest.mark.parametrize("model", ["g1", "g7"])
@pytest.mark.parametrize("bc", [0.2, 0.45])
def test_fit_recovers_known_bc(model, bc):
    assert b.fit_shot(_shot(model, bc), model) == pytest.approx(bc, rel=0.01)


def test_g7_value_is_lower_than_g1_for_same_data():
    s = _shot("g1", 0.5)
    assert b.fit_shot(s, "g7") < b.fit_shot(s, "g1")


def test_noise_is_tolerated():
    assert b.fit_shot(_shot("g1", 0.4, noise=0.5), "g1") == pytest.approx(0.4, rel=0.1)


def test_too_short_track_gives_none():
    assert b.fit_shot(_shot("g1", 0.4, span=6), "g1") is None


def test_series_bc_ignores_excluded_and_reports_counts():
    res = b.series_bc([_shot("g1", 0.4), _shot("g1", 0.42), _shot("g1", 0.1, excluded=True)])
    assert res["g1"]["n"] == 2
    assert res["g1"]["avg"] == pytest.approx(0.41, rel=0.02)
    assert res["g7"]["n"] == 2
    assert b.series_bc([])["g1"] == {"n": 0, "avg": None, "sd": None}


def test_fit_works_with_few_distance_points_without_track():
    xs = [5.0, 30.0, 50.0]
    vs = b._simulate("g1", 0.5, 0.0, 800.0, xs)
    s = Shot(1, datetime(2030, 1, 1), 10.0, 800.0, xs, vs, 3000.0, [], None, None)
    assert b.fit_shot(s, "g1") == pytest.approx(0.5, rel=0.01)  # V0 + 3 Distanzen = 4 Punkte
    s2 = Shot(1, datetime(2030, 1, 1), 10.0, 800.0, xs[:2], vs[:2], 3000.0, [], None, None)
    assert b.fit_shot(s2, "g1") is None  # zu wenige Punkte
