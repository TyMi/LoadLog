"""Statistik über gewertete Schüsse (ausgeschlossene werden ignoriert)."""

import math
from dataclasses import asdict, dataclass

from .models import Shot


@dataclass
class Stats:
    n: int
    avg: float | None
    sd: float | None  # Stichproben-Standardabweichung, erst ab 2 Schuss
    es: float | None
    vmin: float | None
    vmax: float | None
    energy_avg_j: float | None
    mip_avg: float | None = None
    mip_min: float | None = None  # kleinster Wert: vorsichtige Orientierung (die Sportordnung disqualifiziert nur, wenn keine der bis zu drei Messungen den Wert erreicht)

    def as_dict(self) -> dict:
        return asdict(self)


def compute(shots: list[Shot]) -> Stats:
    inc = [s for s in shots if not s.excluded]
    n = len(inc)
    if n == 0:
        return Stats(0, None, None, None, None, None, None)
    vs = [s.v0_ms for s in inc]
    ps = [p for s in inc if (p := s.mip) is not None]
    avg = sum(vs) / n
    sd = math.sqrt(sum((v - avg) ** 2 for v in vs) / (n - 1)) if n > 1 else None
    return Stats(
        n=n,
        avg=avg,
        sd=sd,
        es=max(vs) - min(vs),
        vmin=min(vs),
        vmax=max(vs),
        energy_avg_j=sum(s.energy0_j for s in inc) / n,
        mip_avg=sum(ps) / len(ps) if ps else None,
        mip_min=min(ps) if ps else None,
    )


def linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    """Lineare Regression: (Steigung, Achsenabschnitt) oder None bei < 2 Punkten."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    return slope, my - slope * mx
