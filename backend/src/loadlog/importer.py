"""Import einer LabRadar-SD-Karten-Struktur (ZIP oder Ordner) in Series-Objekte."""

import io
import re
import zipfile
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .csvio import CsvError, parse_report, parse_track, report_to_series, report_units
from .lbr import LbrError, parse_lbr
from .messages import CodedError, Note, reason
from .models import Series

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_FILES = 20000

_LBR = re.compile(r"(?:^|/)SR(\d{3,4})/SR\1\.lbr$", re.I)
_REPORT = re.compile(r"(?:^|/)SR(\d{3,4})/SR\1 Report\.csv$", re.I)
_TRACK = re.compile(r"(?:^|/)SR(\d{3,4})/TRK/Shot(\d{3,4}) Track\.csv$", re.I)


class ImportFailure(CodedError):
    """Die Eingabe ist keine lesbare LabRadar-Struktur."""


@dataclass
class ImportResult:
    series: list[Series] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def drop_insane(series: Series, label: str, warnings: list[str]) -> Series:
    """Verwirft Schüsse mit nicht endlichen oder unplausiblen Werten (NaN/Inf aus manipulierten oder defekten Dateien)."""
    good = [s for s in series.shots if s.is_sane()]
    if len(good) != len(series.shots):
        warnings.append(Note("insane", label=label, n=len(series.shots) - len(good)))
        series.shots = good
    seen: set[int] = set()
    unique = [s for s in series.shots if s.number not in seen and not seen.add(s.number)]  # erster Schuss je Nummer zählt
    if len(unique) != len(series.shots):
        warnings.append(Note("shot_duplicate", label=label, n=len(series.shots) - len(unique)))
        series.shots = unique
    return series


def _norm(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def _relevant(name: str) -> bool:
    return bool(_LBR.search(name) or _REPORT.search(name) or _TRACK.search(name))


def read_zip(data: bytes, warnings: list[str] | None = None) -> dict[str, bytes]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, NotImplementedError, ValueError, OSError) as exc:
        raise ImportFailure("zip_invalid") from exc
    files: dict[str, bytes] = {}
    total = 0
    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise ImportFailure("zip_too_many")
    for info in infos:
        name = _norm(info.filename)
        if info.is_dir() or ".." in name.split("/") or not _relevant(name):
            continue
        if info.file_size > MAX_FILE_BYTES:  # nur diese Datei auslassen, die übrigen Serien bleiben importierbar
            if warnings is not None:
                warnings.append(Note("file_too_large", name=name))
            continue
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise ImportFailure("zip_too_big")
        try:
            files[name] = zf.read(info)
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError, ValueError, OSError):  # falsche Prüfsumme, verschlüsselt, abgeschnitten, beschädigte Kopfdaten
            if warnings is not None:
                warnings.append(Note("file_unreadable", name=name))
    return files


def read_dir(path: Path, warnings: list[str] | None = None) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for p in path.rglob("*"):
        if p.is_file() and not p.is_symlink():
            name = _norm(str(p.relative_to(path)))
            if not _relevant(name):
                continue
            if p.stat().st_size > MAX_FILE_BYTES:
                if warnings is not None:
                    warnings.append(Note("file_too_large", name=name))
                continue
            files[name] = p.read_bytes()
    return files


def collect(files: Mapping[str, bytes], warnings: list[str] | None = None) -> ImportResult:
    lbrs: dict[int, bytes] = {}
    reports: dict[int, bytes] = {}
    tracks: dict[tuple[int, int], bytes] = {}
    for name, data in files.items():
        if m := _LBR.search(name):
            lbrs[int(m.group(1))] = data
        elif m := _REPORT.search(name):
            reports[int(m.group(1))] = data
        elif m := _TRACK.search(name):
            tracks[(int(m.group(1)), int(m.group(2)))] = data

    result = ImportResult(warnings=list(warnings or []))
    for no in sorted(set(lbrs) | set(reports)):
        label = Note("series_label", no=no)
        try:
            rep = parse_report(reports[no]) if no in reports else None
            units = report_units(rep) if rep else None
            if no in lbrs:
                series = parse_lbr(lbrs[no], units)
                series.device_id = rep.device_id if rep else None
                if series.number != no:  # der Kopf kennt die Nummer nur als ein Byte; der Ordnername ist maßgeblich
                    result.warnings.append(Note("series_number_adjusted", label=label, head=series.number))
                    series.number = no
            else:
                assert rep is not None
                series = report_to_series(rep, units)
                result.warnings.append(Note("series_no_lbr", label=label))
        except (LbrError, CsvError) as exc:
            result.warnings.append(Note("series_skipped", label=label, reason=reason(exc)))
            continue
        for shot in series.shots:
            raw = tracks.get((no, shot.number))
            if raw is None:
                continue
            try:
                shot.track = parse_track(raw).points
            except CsvError as exc:
                result.warnings.append(Note("track_ignored", label=label, shot=shot.number, reason=reason(exc)))
        drop_insane(series, label, result.warnings)
        if series.shots:
            result.series.append(series)
    if not result.series:
        raise ImportFailure("no_series")
    return result


def import_zip(data: bytes) -> ImportResult:
    warnings: list[str] = []
    return collect(read_zip(data, warnings), warnings)


def import_dir(path: Path) -> ImportResult:
    warnings: list[str] = []
    return collect(read_dir(path, warnings), warnings)
