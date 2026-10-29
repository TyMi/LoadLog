"""CSV-Export von Schüssen (Serie oder Laborierung), Excel-tauglich."""

import csv
import io

from . import i18n
from .db import SeriesRecord
from .units import d_out, e_out, grains, unit_names, v_out

BOM = "﻿"  # damit Excel UTF-8 (Umlaute) erkennt


def safe(cell: object) -> object:
    """Schutz vor Formel-Einschleusung (CSV-Injection): Text, der mit = + - @ beginnt, wird entschärft."""
    if isinstance(cell, str) and cell[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + cell
    return cell


def _num(x: float | None, decimals: int, lang: str) -> str:
    if x is None:
        return ""
    s = f"{x:.{decimals}f}"
    return s.replace(".", ",") if lang == "de" else s


def shots_csv(rows: list[tuple[str | None, SeriesRecord]], units: str, lang: str) -> str:
    """Eine Zeile je Schuss. `rows` = (Laborierungsname oder None, Serie). Deutsch: Semikolon und Komma, sonst Komma und Punkt."""
    tx = i18n.TEXTS[lang]
    u = unit_names(units)
    dists = sorted({round(d, 1) for _, rec in rows for s in rec.shots for d in s.distances_m})
    head = [tx["load_col"], tx["series"], tx["name"], tx["date"], tx["shot"], tx["time"], f"V0 ({u['v']})",
            f"{tx['bullet_weight']} (gr)", f"E0 ({u['e']})", "MIP", "PF",
            tx["signal"], tx["status"]]
    head += [f"V {_num(d_out(d, units), 1 if units == 'imp' else 0, lang)} {u['d']} ({u['v']})" for d in dists]
    out = io.StringIO()
    w = csv.writer(out, delimiter=";" if lang == "de" else ",", lineterminator="\r\n")
    w.writerow(head)
    for load_name, rec in rows:
        for s in rec.shots:
            at = {round(d, 1): v for d, v in zip(s.distances_m, s.velocities_ms, strict=False)}
            w.writerow([safe(x) for x in [
                load_name or "", rec.number, rec.name or "", s.taken_at.strftime("%Y-%m-%d"), s.number, s.taken_at.strftime("%H:%M:%S"),
                _num(v_out(s.v0_ms, units), 1, lang),
                _num(grains(s.weight_g), 1, lang) if s.weight_g else "",
                _num(e_out(s.energy0_j, units), 0, lang) if s.energy0_j is not None else "",
                _num(s.mip, 0, lang), _num(s.power_factor, 1, lang),
                s.signal_strength if s.signal_strength is not None else "",
                tx["excluded"] if s.excluded else tx["included"],
                *[_num(v_out(at[d], units), 1, lang) if d in at else "" for d in dists],
            ]])
    return BOM + out.getvalue()
