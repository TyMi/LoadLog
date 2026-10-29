"""Datenmodell für importierte LabRadar-Serien (intern immer SI: m/s, m, J, g)."""

import math
from dataclasses import dataclass, field
from datetime import datetime

GRAMS_PER_GRAIN = 0.06479891
MS_PER_FPS = 0.3048
M_PER_YD = 0.9144
M_PER_FT = 0.3048
J_PER_FTLBF = 1.3558179483314


@dataclass(frozen=True)
class DeviceUnits:
    """Einheiten, in denen das Gerät seine Dateien schreibt (Report-Kopf)."""

    velocity: str = "m/s"  # m/s | fps
    distance: str = "m"  # m | yd | ft
    energy: str = "ft-lbf"  # ft-lbf | J
    weight: str = "gr"  # gr | g

    def v(self, x: float) -> float:
        return x * MS_PER_FPS if self.velocity == "fps" else x

    def d(self, x: float) -> float:
        if self.distance == "yd":
            return x * M_PER_YD
        if self.distance == "ft":
            return x * M_PER_FT
        return x

    def e(self, x: float) -> float:
        return x * J_PER_FTLBF if self.energy == "ft-lbf" else x

    def w(self, x: float) -> float:
        return x * GRAMS_PER_GRAIN if self.weight == "gr" else x


@dataclass(frozen=True)
class TrackPoint:
    time_s: float
    velocity_ms: float
    distance_m: float
    snr: float | None  # der erste Punkt hat keinen SNR


@dataclass
class Shot:
    number: int
    taken_at: datetime
    weight_g: float
    v0_ms: float
    distances_m: list[float]  # Dx1..Dx5
    velocities_ms: list[float]
    energy0_j: float
    energies_j: list[float]
    power_factor: float | None
    signal_strength: int | None  # 1..5 Balken am Gerät
    track: list[TrackPoint] = field(default_factory=list)
    excluded: bool = False

    def is_sane(self) -> bool:
        """Alle Zahlen endlich und V0 physikalisch plausibel (0 < V0 < 2000 m/s); sonst wird der Schuss beim Import verworfen."""
        nums = [self.weight_g, self.v0_ms, self.energy0_j, *self.distances_m, *self.velocities_ms, *self.energies_j]
        nums += [x for p in self.track for x in (p.time_s, p.velocity_ms, p.distance_m)]
        return all(math.isfinite(x) for x in nums if x is not None) and 0 < self.v0_ms < 2000

    @property
    def mip(self) -> float | None:
        """Mindestimpuls nach der Sportordnung des Deutschen Schützenbundes (DSB), Teil 2, Regel 2.21.1:
        MIP = 0,1 × Geschossgewicht (g) × Mündungsgeschwindigkeit (m/s); hier mit V0.

        None, wenn das Geschossgewicht unbekannt ist.
        """
        return 0.1 * self.weight_g * self.v0_ms if self.weight_g and self.weight_g > 0 else None


@dataclass
class Series:
    number: int
    shots: list[Shot]
    device_id: str | None = None
    device_avg_ms: float | None = None  # Kopfstatistik der .lbr (alle Schüsse)
    charge_gr: float | None = None  # nur bei GRT-Import vorhanden
    note: str | None = None
    name: str | None = None  # nur bei GRT-Import mit eigenem Namen
