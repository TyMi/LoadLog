"""Umrechnung SI -> Anzeigeeinheiten und Zahlenformat."""

from .messages import CodedError
from .models import GRAMS_PER_GRAIN, J_PER_FTLBF, M_PER_YD, MS_PER_FPS

UNIT_SYSTEMS = ("si", "imp")


def check_units(units: str) -> str:
    if units not in UNIT_SYSTEMS:
        raise CodedError("bad_units", units=units)
    return units


def v_out(v_ms: float, units: str) -> float:
    return v_ms / MS_PER_FPS if units == "imp" else v_ms


def d_out(d_m: float, units: str) -> float:
    return d_m / M_PER_YD if units == "imp" else d_m


def e_out(e_j: float, units: str) -> float:
    return e_j / J_PER_FTLBF if units == "imp" else e_j


def grains(weight_g: float) -> float:
    return weight_g / GRAMS_PER_GRAIN


def unit_names(units: str) -> dict[str, str]:
    if units == "imp":
        return {"v": "fps", "d": "yd", "e": "ft-lbf"}
    return {"v": "m/s", "d": "m", "e": "J"}


def fmt(x: float | None, decimals: int = 1, lang: str = "de") -> str:
    if x is None:
        return "–"
    s = f"{x:.{decimals}f}"
    return s.replace(".", ",") if lang == "de" else s
