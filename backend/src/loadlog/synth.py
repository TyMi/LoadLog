"""Generator für SYNTHETISCHE LabRadar-SD-Karten-Daten (Beispiele, Tests, Screenshots).

Alle Werte sind erfunden: Geräte-ID `LBR-0000000`, Zeitstempel im Jahr 2030.
Echte Messdaten dürfen nie ins Repository.
"""

import io
import math
import random
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from .lbr import build_lbr
from .models import GRAMS_PER_GRAIN, J_PER_FTLBF, MS_PER_FPS

DEVICE_ID = "LBR-0000000"
DEFAULT_DISTANCES = (5, 10, 15, 20, 25)

DEFAULT_SPECS = [
    {"number": 1, "shots": 8, "v0": 284.0, "sd": 5.5, "weight_gr": 180.0},
    {"number": 2, "shots": 10, "v0": 289.0, "sd": 6.5, "weight_gr": 180.0, "nul_pad": True},
    {"number": 3, "shots": 5, "v0": 296.0, "sd": 4.0, "weight_gr": 180.0, "distances": (5, 10, 15, 20, 23)},
]


def _ke(weight_g: float, v: float) -> float:
    return 0.5 * weight_g / 1000 * v * v / J_PER_FTLBF


def _track(rng: random.Random, v0: float, snr_level: float) -> list[tuple[float, float, float, float | None]]:
    drop_per_m = 0.075 + rng.random() * 0.015
    pts = [(0.0, v0, 0.0, None)]
    t, d, v = 0.021, 5.5, v0 - 1.6
    end = 29 + rng.random() * 6
    while d < end:
        v = v - drop_per_m * (v * 0.002 * 1.0) * 1.2 + rng.gauss(0, 0.12)
        snr = max(7.0, snr_level * (1.0 - (d / 45.0) ** 2) + rng.gauss(0, 2.0))
        pts.append((t, v, d, snr))
        step = 0.002
        t += step
        d += v * step
    return pts


def _report(spec: dict, rows: list[dict], dist: tuple, device_id: str) -> str:
    vs = [r["v0"] for r in rows]
    n = len(vs)
    avg = sum(vs) / n
    sd = math.sqrt(sum((v - avg) ** 2 for v in vs) / (n - 1)) if n > 1 else 0.0
    head = [
        "sep=;",
        f"Device ID;{device_id};;",
        "",
        f"Series No;{spec['number']:04d};;",
        f"Total number of shots;{n:04d};;",
        "",
        "Units velocity;m/s;;",
        "Units distances;m;;",
        "Units kinetic energy;ft-lbf;;",
        "Units weight;grain (gr);;",
        "",
        f"Stats - Average;{avg:.2f};m/s;",
        f"Stats - Highest;{max(vs):.2f};m/s;",
        f"Stats - Lowest;{min(vs):.2f};m/s;",
        f"Stats - Ext. Spread;{max(vs) - min(vs):.2f};m/s;",
        f"Stats - Std. Dev;{sd:.2f};m/s;",
        "",
    ]
    cols = (
        ["Shot ID", "V0"] + [f"V{d}" for d in dist] + ["Ke0"] + [f"Ke{d}" for d in dist]
        + [f"PF{dist[0]}", "Proj. Weight", "Date", "Time"]
    )
    body = [";".join(cols) + ";"]
    for r in rows:
        t = r["taken_at"]
        cells = (
            [f"{r['shot']:04d}", f"{r['v0']:.0f}"] + [f"{v:.0f}" for v in r["vs"]]
            + [f"{r['ke0']:.0f}"] + [f"{k:.0f}" for k in r["kes"]]
            + [f"{r['pf']:.2f}", f"{spec['weight_gr']:.2f}", t.strftime("%m-%d-%Y"), t.strftime("%H:%M:%S")]
        )
        body.append(";".join(cells) + ";")
    lines = head + body
    if spec.get("nul_pad"):
        lines = [lines[0]] + ["\x00" + ln.ljust(61) for ln in lines[1:]]
    return "\r\n".join(lines) + "\r\n"


def make_sd_card(seed: int = 1, specs: list[dict] | None = None) -> dict[str, bytes]:
    """Liefert {relativer Pfad: Bytes} einer synthetischen SD-Karte (`LBR/...`)."""
    rng = random.Random(seed)
    files: dict[str, bytes] = {"LBR/LBR0000000203001011200.LID": b""}
    clock = datetime(2030, 1, 15, 10, 0, 0)
    for spec in specs or DEFAULT_SPECS:
        dist = tuple(spec.get("distances", DEFAULT_DISTANCES))
        weight_g = spec["weight_gr"] * GRAMS_PER_GRAIN
        rows = []
        for i in range(1, spec["shots"] + 1):
            clock += timedelta(seconds=rng.randint(6, 40))
            v0 = rng.gauss(spec["v0"], spec["sd"])
            track = _track(rng, v0, snr_level=rng.choice([14, 22, 28, 32, 34]))
            decay = (track[-1][1] - v0) / track[-1][2]
            vs = [v0 + decay * d for d in dist]
            snr_mean = sum(p[3] for p in track if p[3]) / (len(track) - 1)
            rows.append({
                "shot": i, "taken_at": clock, "weight_g": weight_g, "v0": v0, "ke0": _ke(weight_g, v0),
                "pf": spec["weight_gr"] * (vs[0] / MS_PER_FPS) / 1000,
                "vs": vs, "ds": [float(d) for d in dist], "kes": [_ke(weight_g, v) for v in vs],
                "signal": max(1, min(5, round(snr_mean / 7))), "track": track,
            })
        sr = f"LBR/SR{spec['number']:04d}"
        files[f"{sr}/SR{spec['number']:04d}.lbr"] = build_lbr(spec["number"], rows)
        files[f"{sr}/SR{spec['number']:04d} Report.csv"] = _report(spec, rows, dist, DEVICE_ID).encode("latin-1")
        for r in rows:
            lines = [
                "sep=;", f"Device ID;{DEVICE_ID};;", f"Series No;{spec['number']:04d}",
                f"Shot No;{r['shot']:04d}", "", "Time (s);Vel (m/s);Dist (m);SNR",
            ]
            for t, v, d, snr in r["track"]:
                lines.append(f"{t:.6f};{v:.2f};{d:.2f};{'-' if snr is None else f'{snr:.2f}'}")
            files[f"{sr}/TRK/Shot{r['shot']:04d} Track.csv"] = ("\r\n".join(lines) + "\r\n").encode()
    return files


def make_zip(seed: int = 1, specs: list[dict] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in make_sd_card(seed, specs).items():
            zf.writestr(name, data)
    return buf.getvalue()


def write_sd_card(target: Path, seed: int = 1, specs: list[dict] | None = None) -> None:
    for name, data in make_sd_card(seed, specs).items():
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def make_grtload(seed: int = 1) -> bytes:
    """Synthetische GRT-Datei (.grtload): Laborierung mit Ladeleiter (je 5 Schuss mit Track), einer
    Serie ohne Track und einem Doppel der Serien-Nr. (wie bei mehreren SD-Karten)."""
    from urllib.parse import quote

    rnd = random.Random(seed)
    weight_g = 180 * GRAMS_PER_GRAIN
    dists = (5, 25, 50)
    t0 = datetime(2030, 3, 1, 10, 0, 0)

    def shot_xml(i: int, v0: float, when: datetime, track: bool) -> str:
        vals = {d: round(v0 - 0.65 * d + rnd.gauss(0, 0.4)) for d in dists}
        attrs = (f'name="Shot{i}" velocity="{round(v0)}" pressure="0" V0="{round(v0)}" '
                 + " ".join(f'V{d}="{v}"' for d, v in vals.items())
                 + f' note="{quote(when.strftime("%m-%d-%Y %H:%M:%S"))}" showtrackdiagraminreport="true"')
        pts = ""
        if track:
            for k in range(30):
                d = k * 1.7
                pts += f'<track time="{k * 1.0 + (8 if k else 0):.3f}" velo="{v0 - 0.65 * d + rnd.gauss(0, 0.2):.2f}" dist="{d:.2f}"/>'
        return f"<shot {attrs}>{pts}</shot>"

    def series_xml(name: str, charge_gr: float, v0: float, shots: int, start: datetime, track: bool = True) -> str:
        body = "".join(shot_xml(i + 1, v0 + rnd.gauss(0, 2.5), start + timedelta(seconds=25 * i), track) for i in range(shots))
        menu = quote(";".join(["V0", *(f"V{d}" for d in dists)]))
        return (f'<charge name="{quote(name)}" showinreport="true" expanded="false" expandedstats="false" '
                f'note="{quote("Synthetisch")}" value="{charge_gr * GRAMS_PER_GRAIN / 1000:.12f}" menu="{menu}" '
                f'menuvalue="V0" menuunit="m" source="Labradar" sourceoptions="%7B%7D">{body}</charge>')

    def inp(name: str, value: str, unit: str = "", typ: str = "string") -> str:
        return f'<input name="{name}" value="{quote(value)}" unit="{unit}" type="{typ}" descr=""/>'

    series = "".join([
        series_xml("Series 1", 40.0, 780.0, 5, t0),
        series_xml("Series 2", 40.5, 786.0, 5, t0 + timedelta(minutes=10)),
        series_xml("Series 3", 41.0, 792.0, 5, t0 + timedelta(minutes=20)),
        series_xml("Series 1", 41.5, 797.0, 4, t0 + timedelta(days=1)),  # gleiche Nr., andere Karte
        series_xml("Handnotiz", 42.0, 800.0, 3, t0 + timedelta(days=2), track=False),
    ])
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\r\n'
        "<GordonsReloadingTool version='2021.0000-SYNTHETIC'><InnerBallistikInput>"
        f"<title>{quote('.308 Win. Synthetisch, Testgeschoss 180 grain, Testpulver')}</title>"
        f"<gun>{inp('xe', '600', 'mm', 'decimal')}</gun>"
        f"<caliber>{inp('CaliberName', '.308 Win. (synthetisch)')}{inp('oal', '71.5', 'mm', 'decimal')}</caliber>"
        f"<projectile>{inp('mname', 'Testhersteller')}{inp('pname', 'Testgeschoss')}{inp('lotid', 'L-1')}"
        f"{inp('mp', str(weight_g), 'g', 'decimal')}{inp('gdepth', '10.5', 'mm', 'decimal')}</projectile>"
        f"<propellant>{inp('mname', 'Testpulver GmbH')}{inp('pname', 'TP-1')}{inp('lotid', 'P-7')}</propellant>"
        f"<appendix><Measurement index='1' showinreport='false' title='Measurement'>{series}</Measurement>"
        "<note/></appendix></InnerBallistikInput></GordonsReloadingTool>"
    )
    return xml.encode()


if __name__ == "__main__":  # python -m loadlog.synth <zielordner>
    import sys

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "synthetic-sd")
    write_sd_card(out)
    print(f"Synthetische SD-Karte geschrieben nach {out}")
