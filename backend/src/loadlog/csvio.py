"""Parser für `SRnnnn Report.csv` und `ShotNNNN Track.csv`.

Die Dateien enthalten teils NUL-Bytes als Zeilenauffüllung (UTF-16-Artefakt).
Spaltennamen werden dynamisch gelesen, weil die Messdistanzen am Gerät einstellbar sind.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from .messages import CodedError
from .models import DeviceUnits, Series, Shot, TrackPoint


class CsvError(CodedError):
    pass


def _lines(raw: bytes) -> list[str]:
    text = raw.replace(b"\x00", b"").decode("latin-1")
    return [ln.strip() for ln in text.splitlines()]


@dataclass
class Report:
    head: dict[str, tuple[str, str]] = field(default_factory=dict)
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)

    @property
    def device_id(self) -> str | None:
        v = self.head.get("Device ID")
        return v[0] if v and v[0] else None

    @property
    def series_number(self) -> int | None:
        v = self.head.get("Series No")
        return int(v[0]) if v and v[0].isdigit() else None


def parse_report(raw: bytes) -> Report:
    rep = Report()
    for ln in _lines(raw):
        if not ln or ln.startswith("sep="):
            continue
        cells = [c.strip() for c in ln.split(";")]
        if cells[0] == "Shot ID":
            rep.columns = [c for c in cells if c]
        elif rep.columns:
            rep.rows.append(dict(zip(rep.columns, cells, strict=False)))
        elif len(cells) >= 2:
            rep.head[cells[0]] = (cells[1], cells[2] if len(cells) > 2 else "")
    return rep


def report_units(rep: Report) -> DeviceUnits:
    def val(key: str) -> str:
        return rep.head.get(key, ("", ""))[0].lower()

    vel, dist, en, wt = val("Units velocity"), val("Units distances"), val("Units kinetic energy"), val("Units weight")
    return DeviceUnits(
        velocity="fps" if ("fps" in vel or "ft/s" in vel) else "m/s",
        distance="yd" if "yd" in dist else ("ft" if dist.startswith("ft") or dist == "feet" else "m"),
        energy="ft-lbf" if "ft" in en or not en else "J",
        weight="g" if wt.startswith("g") and "gr" not in wt else "gr",
    )


def _parse_dt(date: str, time: str) -> datetime:
    for fmt in ("%m-%d-%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(f"{date} {time}", fmt)
        except ValueError:
            continue
    raise CsvError("csv_datetime", date=date, time=time)


def report_to_series(rep: Report, units: DeviceUnits | None = None) -> Series:
    """Fallback ohne `.lbr`: baut die Serie aus den (gerundeten) Report-Werten."""
    units = units or report_units(rep)
    number = rep.series_number
    if number is None:
        raise CsvError("csv_no_series")
    v_cols = sorted((int(m.group(1)), c) for c in rep.columns if (m := re.fullmatch(r"V(\d+)", c)))
    dist_cols = [(d, c) for d, c in v_cols if d > 0]
    ke_names = {int(m.group(1)): c for c in rep.columns if (m := re.fullmatch(r"Ke(\d+)", c))}
    pf_col = next((c for c in rep.columns if c.startswith("PF")), None)
    shots = []
    for row in rep.rows:
        if not row.get("Shot ID", "").isdigit():
            continue
        try:
            shots.append(
                Shot(
                    number=int(row["Shot ID"]),
                    taken_at=_parse_dt(row["Date"], row["Time"]),
                    weight_g=units.w(float(row.get("Proj. Weight", "0") or 0)),
                    v0_ms=units.v(float(row["V0"])),
                    distances_m=[units.d(float(d)) for d, _ in dist_cols],
                    velocities_ms=[units.v(float(row[c])) for _, c in dist_cols],
                    energy0_j=units.e(float(row.get("Ke0", "0") or 0)),
                    energies_j=[units.e(float(row[ke_names[d]])) for d, _ in dist_cols if d in ke_names],
                    power_factor=float(row[pf_col]) if pf_col and row.get(pf_col) else None,
                    signal_strength=None,
                )
            )
        except (KeyError, ValueError) as exc:
            raise CsvError("csv_bad_row", row=str(row)) from exc
    return Series(number=number, shots=shots, device_id=rep.device_id)


@dataclass
class TrackFile:
    meta: dict[str, str]
    points: list[TrackPoint]


def _unit_of(header: str) -> str:
    m = re.search(r"\(([^)]*)\)", header)
    return m.group(1).strip().lower() if m else ""


def parse_track(raw: bytes) -> TrackFile:
    meta: dict[str, str] = {}
    points: list[TrackPoint] = []
    vel_unit = dist_unit = ""
    in_table = False
    for ln in _lines(raw):
        if not ln or ln.startswith("sep="):
            continue
        cells = [c.strip() for c in ln.split(";")]
        if cells[0].lower().startswith("time"):
            in_table = True
            vel_unit = _unit_of(cells[1]) if len(cells) > 1 else ""
            dist_unit = _unit_of(cells[2]) if len(cells) > 2 else ""
        elif in_table:
            if len(cells) < 3:
                continue
            try:
                snr = None if len(cells) < 4 or cells[3] in ("", "-") else float(cells[3])
                points.append(TrackPoint(float(cells[0]), float(cells[1]), float(cells[2]), snr))
            except ValueError as exc:
                raise CsvError("csv_bad_track", line=ln) from exc
        elif len(cells) >= 2:
            meta[cells[0]] = cells[1]
    units = DeviceUnits(
        velocity="fps" if vel_unit in ("fps", "ft/s") else "m/s",
        distance="yd" if dist_unit == "yd" else ("ft" if dist_unit == "ft" else "m"),
    )
    points = [TrackPoint(p.time_s, units.v(p.velocity_ms), units.d(p.distance_m), p.snr) for p in points]
    return TrackFile(meta=meta, points=points)
