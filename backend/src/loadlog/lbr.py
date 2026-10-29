"""Parser und Writer für das Binärformat `SRnnnn.lbr` (siehe docs/labradar-format.md).

28 Byte Kopf, danach 100 Byte je Schuss, little-endian.
"""

import struct
from datetime import datetime

from .messages import CodedError
from .models import DeviceUnits, Series, Shot

HEADER_SIZE = 28
RECORD_SIZE = 100

_HEADER = struct.Struct("<BBBB4s5f")
_RECORD = struct.Struct(
    "<BxB"  # Serie, -, Schuss
    "5BH2x"  # Sekunde, Minute, Stunde, Tag, Monat, Jahr
    "f f I"  # Gewicht (g), Konstante 0,15, Flag
    "f f f"  # V0, Ke0, PF
    "5f 5f 5f"  # V(Dx), Distanzen, Ke(Dx)
    "I"  # Signalstärke
)

assert _HEADER.size == HEADER_SIZE
assert _RECORD.size == RECORD_SIZE


class LbrError(CodedError):
    pass


def parse_lbr(data: bytes, units: DeviceUnits | None = None) -> Series:
    """Liest eine `.lbr`-Datei. `units` sind die Geräteeinheiten (Standard: m/s, m, ft-lbf)."""
    units = units or DeviceUnits()
    if len(data) < HEADER_SIZE or (len(data) - HEADER_SIZE) % RECORD_SIZE:
        raise LbrError("lbr_size", bytes=len(data))
    _ver, n_shots, series_no, _zero, _unk, avg, *_ = _HEADER.unpack_from(data)
    if n_shots != (len(data) - HEADER_SIZE) // RECORD_SIZE:
        raise LbrError("lbr_count")

    shots = []
    for i in range(n_shots):
        f = _RECORD.unpack_from(data, HEADER_SIZE + i * RECORD_SIZE)
        _ser, shot_no, sec, minute, hour, day, month, year = f[:8]
        weight_g, _const, _flag, v0, ke0, pf = f[8:14]
        try:
            taken = datetime(year, month, day, hour, minute, sec)
        except ValueError as exc:
            raise LbrError("lbr_time", shot=i + 1) from exc
        sig = f[29] if 1 <= f[29] <= 5 else None
        shots.append(
            Shot(
                number=shot_no,
                taken_at=taken,
                weight_g=weight_g,
                v0_ms=units.v(v0),
                velocities_ms=[units.v(x) for x in f[14:19]],
                distances_m=[units.d(x) for x in f[19:24]],
                energy0_j=units.e(ke0),
                energies_j=[units.e(x) for x in f[24:29]],
                power_factor=pf,
                signal_strength=sig,
            )
        )
    return Series(number=series_no, shots=shots, device_avg_ms=units.v(avg))


def build_lbr(series_no: int, records: list[dict], flag: int = 1) -> bytes:
    """Erzeugt eine `.lbr` (für den synthetischen Generator und Tests).

    Jeder Eintrag: shot, taken_at, weight_g, v0, ke0, pf, vs[5], ds[5], kes[5], signal.
    Werte in Geräteeinheiten.
    """
    v0s = [r["v0"] for r in records]
    avg = sum(v0s) / len(v0s)
    n = len(v0s)
    sd = (sum((v - avg) ** 2 for v in v0s) / (n - 1)) ** 0.5 if n > 1 else 0.0
    out = bytearray(
        _HEADER.pack(1, n, series_no, 0, b"\xb9X\x00\x10", avg, max(v0s), min(v0s),
                     max(v0s) - min(v0s), sd)
    )
    for r in records:
        t = r["taken_at"]
        out += _RECORD.pack(
            series_no, r["shot"], t.second, t.minute, t.hour, t.day, t.month, t.year,
            r["weight_g"], 0.15, flag, r["v0"], r["ke0"], r["pf"],
            *r["vs"], *r["ds"], *r["kes"], r["signal"],
        )
    return bytes(out)
