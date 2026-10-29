"""Import von GRT-Dateien (`.grtload`, Gordon's Reloading Tool): Laborierung samt eingebetteten LabRadar-Serien.

Das Format ist XML. Unter `InnerBallistikInput/appendix/Measurement` liegt je Serie ein `charge`-Element
(Name, Pulvermenge in kg, Notiz, Schüsse mit V0, Geschwindigkeiten an festen Distanzen und optional dem
Track). Die Kopfdaten stehen in `projectile`, `propellant` und `caliber`. Nicht enthalten sind Signalstärke,
SNR und Geräte-ID; V0 und die Geschwindigkeiten an den Distanzen sind auf 1 m/s gerundet.
"""

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote

from .importer import drop_insane
from .messages import CodedError, Note
from .models import GRAMS_PER_GRAIN, Series, Shot, TrackPoint

MAX_GRT_BYTES = 50 * 1024 * 1024
_KG_PER_GRAIN = GRAMS_PER_GRAIN / 1000
_DATE_FORMATS = ("%m-%d-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S")


class GrtError(CodedError):
    """Die Datei ist keine lesbare GRT-Datei."""


@dataclass
class GrtImport:
    load: dict
    series: list[Series] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _inputs(section: ET.Element | None) -> dict[str, str]:
    return {i.get("name", ""): unquote(i.get("value", "")) for i in section.findall("input")} if section is not None else {}


def _num(text: str | None) -> float | None:
    try:
        x = float(text) if text not in (None, "") else None
    except ValueError:
        return None
    return x if x is None or math.isfinite(x) else None


def _date(text: str) -> datetime | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def looks_like_grt(data: bytes) -> bool:
    return b"<GordonsReloadingTool" in data[:2048]


def _load_header(root: ET.Element) -> dict:
    proj, prop, cal = (_inputs(root.find(s)) for s in ("projectile", "propellant", "caliber"))
    gun = _inputs(root.find("gun"))
    bullet_g = _num(proj.get("mp"))
    notes = [f"Kaliber: {cal['CaliberName']}"] if cal.get("CaliberName") else []
    if (barrel := _num(gun.get("xe"))) and barrel > 0:
        notes.append(f"Lauflänge: {barrel:g} mm")
    notes.append("Importiert aus GRT")
    load = {
        "name": unquote(root.findtext("title") or "GRT-Import").strip()[:200] or "GRT-Import",
        "powder_maker": prop.get("mname") or None,
        "powder_name": prop.get("pname") or None,
        "powder_lot": prop.get("lotid") or None,
        "bullet_maker": proj.get("mname") or None,
        "bullet_type": proj.get("pname") or None,
        "bullet_weight_gr": round(bullet_g / GRAMS_PER_GRAIN, 2) if bullet_g else None,
        "bullet_lot": proj.get("lotid") or None,
        "coal_mm": round(oal, 2) if (oal := _num(cal.get("oal"))) else None,
        "seating_depth_mm": round(depth, 2) if (depth := _num(proj.get("gdepth"))) else None,
        "notes": "\n".join(notes),
    }
    return {k: v for k, v in load.items() if v is not None}


def _track(shot: ET.Element) -> list[TrackPoint] | None:
    """Trackpunkte eines Schusses (Zeit in ms); None, wenn Werte fehlen oder keine Zahlen sind."""
    out = []
    for t in shot.findall("track"):
        vals = [_num(t.get(k, "0")) for k in ("time", "velo", "dist")]
        if any(v is None for v in vals):
            return None
        out.append(TrackPoint(vals[0] / 1000, vals[1], vals[2], None))
    return out


def _series(el: ET.Element, weight_g: float, warnings: list[str]) -> Series | None:
    name = unquote(el.get("name", ""))
    m = re.search(r"(\d+)\s*$", name)
    label = name or "?"
    dists = [float(d) for d in re.findall(r"V(\d+(?:\.\d+)?)", unquote(el.get("menu", ""))) if d != "0"]
    shots: list[Shot] = []
    for i, s in enumerate(el.iter("shot"), 1):
        taken = _date(unquote(s.get("note", "")))
        v0 = _num(s.get("V0")) or _num(s.get("velocity"))
        if taken is None or not v0:
            warnings.append(Note("grt_shot_skipped", label=label, shot=i))
            continue
        track = _track(s)
        if track is None:
            warnings.append(Note("grt_track_invalid", label=label, shot=i))
            track = []
        if track and abs(track[0].velocity_ms - v0) <= 1:
            v0 = track[0].velocity_ms  # der Track ist genauer als die gerundete Angabe
        pairs = [(d, v) for d in dists if (v := _num(s.get(f"V{d:g}"))) and v > 0]
        shots.append(Shot(
            number=i, taken_at=taken, weight_g=weight_g, v0_ms=v0,
            distances_m=[d for d, _ in pairs], velocities_ms=[v for _, v in pairs],
            energy0_j=0.5 * weight_g / 1000 * v0 ** 2, energies_j=[0.5 * weight_g / 1000 * v ** 2 for _, v in pairs],
            power_factor=None, signal_strength=None, track=track,
        ))
    if not shots:
        warnings.append(Note("grt_series_empty", label=label))
        return None
    charge_kg = _num(el.get("value"))
    series = Series(
        number=int(m.group(1)) if m else 0, shots=shots,
        name=None if not name.strip() or re.fullmatch(r"(?i)series\s*\d+", name.strip()) else name.strip()[:200],
        charge_gr=round(charge_kg / _KG_PER_GRAIN, 2) if charge_kg else None,
        note=unquote(el.get("note", "")).strip() or None,
    )
    drop_insane(series, label, warnings)
    return series if series.shots else None


def parse_grtload(data: bytes) -> GrtImport:
    if len(data) > MAX_GRT_BYTES:
        raise GrtError("grt_too_large")
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:  # keine Entity-Tricks aus fremden Dateien
        raise GrtError("grt_doctype")
    if data[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in data[:64]:  # UTF-16/32 würde die DOCTYPE-Prüfung oben umgehen
        raise GrtError("grt_bad_xml", reason="UTF-16/32")
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, LookupError) as exc:  # LookupError: unbekannte Zeichenkodierung im XML-Kopf
        raise GrtError("grt_bad_xml", reason=str(exc)) from exc
    base = root.find("InnerBallistikInput")
    if root.tag != "GordonsReloadingTool" or base is None:
        raise GrtError("grt_not_grt")
    weight_g = _num(_inputs(base.find("projectile")).get("mp")) or 0.0
    result = GrtImport(load=_load_header(base))
    measurement = base.find("appendix/Measurement")
    for el in measurement.findall("charge") if measurement is not None else []:
        if s := _series(el, weight_g, result.warnings):
            result.series.append(s)
    if not result.series:
        raise GrtError("grt_no_series")
    if not weight_g:
        result.warnings.append(Note("grt_weight_missing"))
    charges = {s.charge_gr for s in result.series if s.charge_gr}
    result.load["trial_type"] = "ladder" if len(charges) > 1 else "single"
    return result
