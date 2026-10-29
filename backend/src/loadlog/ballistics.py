"""Ballistischer Koeffizient (BC) aus gemessenen Geschwindigkeit-über-Distanz-Daten.

Pro Schuss wird der BC gesucht, mit dem die Standard-Widerstandsfunktion (G1 oder G7) die gemessene
Geschwindigkeitsabnahme am besten nachbildet (kleinste Fehlerquadrate). Angenommen wird die ICAO-
Standardatmosphäre auf Meereshöhe (15 °C, 1013,25 hPa); Temperatur und Höhe fließen nicht ein.
BC in lb/in² (die übliche Angabe der Hersteller).
"""
import math
from bisect import bisect_right
from dataclasses import asdict, dataclass

from py_ballisticcalc.drag_tables import TableG1, TableG7

from .models import Shot

RHO = 1.225  # kg/m³, ICAO-Standard
SOUND = 340.294  # m/s bei 15 °C
LB_IN2_TO_KG_M2 = 703.0696
MIN_POINTS, MIN_SPAN_M = 4, 8.0
BC_LO, BC_HI = 0.05, 2.0
STEP_M = 1.0

_TABLES = {
    "g1": ([p["Mach"] for p in TableG1], [p["CD"] for p in TableG1]),
    "g7": ([p["Mach"] for p in TableG7], [p["CD"] for p in TableG7]),
}


def _cd(model: str, mach: float) -> float:
    xs, ys = _TABLES[model]
    if mach <= xs[0]:
        return ys[0]
    if mach >= xs[-1]:
        return ys[-1]
    i = bisect_right(xs, mach)
    f = (mach - xs[i - 1]) / (xs[i] - xs[i - 1])
    return ys[i - 1] + f * (ys[i] - ys[i - 1])


def _dvdx(model: str, v: float, bc: float) -> float:
    return -0.5 * RHO * v * (math.pi / 4) * _cd(model, v / SOUND) / (bc * LB_IN2_TO_KG_M2)


def _simulate(model: str, bc: float, x0: float, v0: float, xs: list[float]) -> list[float]:
    """Geschwindigkeit an den Distanzen xs (aufsteigend, ab x0) per RK4."""
    out, x, v = [], x0, v0
    for target in xs:
        while x < target - 1e-9:
            h = min(STEP_M, target - x)
            k1 = _dvdx(model, v, bc)
            k2 = _dvdx(model, v + h / 2 * k1, bc)
            k3 = _dvdx(model, v + h / 2 * k2, bc)
            k4 = _dvdx(model, v + h * k3, bc)
            v += h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            x += h
        out.append(v)
    return out


def _points(shot: Shot) -> list[tuple[float, float]]:
    if shot.track:
        pts = [(p.distance_m, p.velocity_ms) for p in shot.track]
    else:
        pts = [(0.0, shot.v0_ms), *zip(shot.distances_m, shot.velocities_ms, strict=False)]
    pts = sorted({d: v for d, v in pts if v > 0}.items())
    return pts


def fit_shot(shot: Shot, model: str) -> float | None:
    """BC eines Schusses oder None, wenn zu wenige/zu kurze Messdaten vorliegen."""
    pts = _points(shot)
    if len(pts) < MIN_POINTS or pts[-1][0] - pts[0][0] < MIN_SPAN_M:
        return None
    x0, v0 = pts[0]
    xs, vs = [p[0] for p in pts[1:]], [p[1] for p in pts[1:]]

    def sse(bc: float) -> float:
        return sum((m - v) ** 2 for m, v in zip(_simulate(model, bc, x0, v0, xs), vs, strict=True))

    grid = [BC_LO * (BC_HI / BC_LO) ** (i / 24) for i in range(25)]
    k = min(range(len(grid)), key=lambda i: sse(grid[i]))
    a, b = grid[max(k - 1, 0)], grid[min(k + 1, len(grid) - 1)]
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = sse(c), sse(d)
    for _ in range(30):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = sse(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = sse(d)
    bc = (a + b) / 2
    # Am Suchrand ist die Anpassung nicht aussagekräftig (z. B. praktisch keine Abnahme messbar)
    return None if bc <= BC_LO * 1.01 or bc >= BC_HI * 0.99 else bc


@dataclass
class BcResult:
    n: int
    avg: float | None
    sd: float | None

    def as_dict(self) -> dict:
        return asdict(self)


def series_bc(shots: list[Shot]) -> dict[str, dict]:
    """Mittlerer BC (G1 und G7) über die gewerteten Schüsse einer Serie."""
    inc = [s for s in shots if not s.excluded]
    out = {}
    for model in ("g1", "g7"):
        vals = [b for s in inc if (b := fit_shot(s, model)) is not None]
        n = len(vals)
        avg = sum(vals) / n if n else None
        sd = math.sqrt(sum((v - avg) ** 2 for v in vals) / (n - 1)) if n > 1 and avg is not None else None
        out[model] = BcResult(n, avg, sd).as_dict()
    return out
