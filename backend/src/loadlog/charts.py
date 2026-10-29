"""SVG-Diagramme (Serverseitig, für die Oberfläche und die PDF-Berichte)."""

import math
from xml.sax.saxutils import escape

from . import i18n
from .db import SeriesRecord
from .stats import Stats, linear_fit
from .units import d_out, fmt, unit_names, v_out

PALETTES = {
    "dark": {"bg": "#171e27", "grid": "#2a3646", "axis": "#3b4a5e", "text": "#a3b0c0",
             "fg": "#e8edf3", "line": "#6db3ff", "sel": "#f5a623", "excl": "#8794a5", "band": "#6db3ff"},
    "light": {"bg": "#ffffff", "grid": "#d9dfe7", "axis": "#8a96a5", "text": "#4a5563",
              "fg": "#111820", "line": "#2f7fd1", "sel": "#c97400", "excl": "#8a96a5", "band": "#2f7fd1"},
}
FONT = "'IBM Plex Sans', 'DejaVu Sans', Arial, sans-serif"
W, H = 720, 320
ML, MR, MT, MB = 58, 18, 18, 44


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    out, x = [], start
    while x < hi + step * 0.999:
        out.append(round(x, 10))
        if x >= hi:
            break
        x += step
    return out


def _label(x: float, step: float, lang: str) -> str:
    return fmt(x, 0 if step >= 1 else (1 if step >= 0.1 else 2), lang)


class _Frame:
    """Koordinatensystem mit Achsen und Gitter."""

    def __init__(self, xlo, xhi, ylo, yhi, p, lang, xlabel, ylabel, xticks=None):
        self.p, self.lang = p, lang
        self.yt = _ticks(ylo, yhi, 5)
        self.ylo, self.yhi = self.yt[0], self.yt[-1]
        self.xt = xticks if xticks is not None else _ticks(xlo, xhi, 6)
        self.xlo = min(xlo, self.xt[0]) if xticks is None else xlo
        self.xhi = max(xhi, self.xt[-1]) if xticks is None else xhi
        if self.xhi - self.xlo < 1e-9:
            self.xhi = self.xlo + 1
        self.xlabel, self.ylabel = xlabel, ylabel

    def x(self, v: float) -> float:
        return ML + (v - self.xlo) / (self.xhi - self.xlo) * (W - ML - MR)

    def y(self, v: float) -> float:
        return MT + (self.yhi - v) / (self.yhi - self.ylo) * (H - MT - MB)

    def axes(self, xlabels: dict[float, str] | None = None) -> str:
        p, out = self.p, []
        ystep = self.yt[1] - self.yt[0] if len(self.yt) > 1 else 1
        for v in self.yt:
            y = self.y(v)
            out.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}" stroke="{p["grid"]}"/>')
            out.append(f'<text x="{ML - 6}" y="{y + 4:.1f}" fill="{p["text"]}" font-size="11" '
                       f'text-anchor="end">{_label(v, ystep, self.lang)}</text>')
        out.append(f'<line x1="{ML}" y1="{H - MB}" x2="{W - MR}" y2="{H - MB}" stroke="{p["axis"]}"/>')
        xstep = self.xt[1] - self.xt[0] if len(self.xt) > 1 else 1
        for v in self.xt:
            if v < self.xlo - 1e-9 or v > self.xhi + 1e-9:
                continue
            if xlabels is not None and v not in xlabels:
                continue  # ausgedünnte Beschriftung (viele Spalten)
            txt = xlabels[v] if xlabels else _label(v, xstep, self.lang)
            out.append(f'<text x="{self.x(v):.1f}" y="{H - MB + 16}" fill="{p["text"]}" font-size="11" '
                       f'text-anchor="middle">{escape(txt)}</text>')
        out.append(f'<text x="{(ML + W - MR) / 2:.0f}" y="{H - 6}" fill="{p["text"]}" font-size="11" '
                   f'text-anchor="middle">{escape(self.xlabel)}</text>')
        out.append(f'<text x="12" y="{(MT + H - MB) / 2:.0f}" fill="{p["text"]}" font-size="11" '
                   f'text-anchor="middle" transform="rotate(-90 12 {(MT + H - MB) / 2:.0f})">'
                   f'{escape(self.ylabel)}</text>')
        return "".join(out)


def _svg(body: str, p: dict, aria: str, theme: str) -> str:
    bg = f'<rect width="{W}" height="{H}" fill="{p["bg"]}"/>' if theme == "light" else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{escape(aria, {chr(34): "&quot;"})}" font-family="{FONT}">{bg}{body}</svg>')


def _empty(lang: str, theme: str) -> str:
    p = PALETTES[theme]
    txt = f'<text x="{W / 2}" y="{H / 2}" fill="{p["text"]}" text-anchor="middle">{i18n.t(lang, "no_data")}</text>'
    return _svg(txt, p, i18n.t(lang, "no_data"), theme)


def _shot_points(shot) -> list[tuple[float, float]]:
    if shot.track:
        return [(pt.distance_m, pt.velocity_ms) for pt in shot.track]
    return [(0.0, shot.v0_ms), *zip(shot.distances_m, shot.velocities_ms, strict=False)]


def track_chart(rec: SeriesRecord, *, selected: int | None = None, units: str = "si",
                lang: str = "de", theme: str = "dark") -> str:
    """Alle Schuss-Tracks einer Serie überlagert (Geschwindigkeit über Distanz)."""
    p, un = PALETTES[theme], unit_names(units)
    pts = {s.number: [(d_out(d, units), v_out(v, units)) for d, v in _shot_points(s)] for s in rec.shots}
    allp = [pt for v in pts.values() for pt in v]
    if not allp:
        return _empty(lang, theme)
    f = _Frame(0, max(d for d, _ in allp), min(v for _, v in allp), max(v for _, v in allp), p, lang,
               f"{i18n.t(lang, 'distance')} ({un['d']})", f"{i18n.t(lang, 'velocity')} ({un['v']})")
    order = sorted(rec.shots, key=lambda s: s.number == selected)  # gewählter Schuss zuletzt
    lines = []
    for s in order:
        coords = " ".join(f"{f.x(d):.1f},{f.y(v):.1f}" for d, v in pts[s.number])
        if s.excluded:  # ausgeschlossen: immer grau und gestrichelt, gewählt nur dicker
            style = (f'stroke="{p["excl"]}" stroke-width="{3 if s.number == selected else 1.4}" '
                     f'stroke-dasharray="5 4" opacity="{1 if s.number == selected else 0.85}"')
        elif s.number == selected:
            style = f'stroke="{p["sel"]}" stroke-width="3" opacity="1"'
        else:
            style = f'stroke="{p["line"]}" stroke-width="1.6" opacity="0.65"'
        label = f"{i18n.t(lang, 'shot')} {s.number}" + (f" ({i18n.t(lang, 'excluded')})" if s.excluded else "")
        vals = ";".join(f"{fmt(d, 1, lang)} {un['d']} · {fmt(v, 1, lang)} {un['v']}" for d, v in pts[s.number])
        q = {chr(34): "&quot;"}
        lines.append(f'<polyline points="{coords}" fill="none" {style} data-shot="{s.number}" data-label="{escape(label, q)}" '
                     f'data-vals="{escape(vals, q)}"/>')
    return _svg(f.axes() + "".join(lines), p, i18n.t(lang, "aria_track"), theme)


def strip_chart(columns: list[tuple[str, SeriesRecord, Stats]], *, trend: bool = True, units: str = "si",
                lang: str = "de", theme: str = "dark") -> str:
    """V0 aller Schüsse je Serie als Punktewolke mit Mittelwert, ±1 SD und optionalem Trend."""
    p, un = PALETTES[theme], unit_names(units)
    vals = [v_out(s.v0_ms, units) for _, rec, _ in columns for s in rec.shots]
    if not vals:
        return _empty(lang, theme)
    n = len(columns)
    f = _Frame(0.5, n + 0.5, min(vals), max(vals), p, lang, "", f"V0 ({un['v']})", xticks=[float(i + 1) for i in range(n)])
    skip = max(1, math.ceil(n / 12))  # höchstens ~12 Beschriftungen, sonst überlappen sie
    out = [f.axes({float(i + 1): lab for i, (lab, _, _) in enumerate(columns) if i % skip == 0})]
    half = 0.28
    means: list[tuple[float, float]] = []
    jit = [-0.16, 0.1, -0.08, 0.14, -0.03, 0.12, -0.12, 0.06, -0.06, 0.16]
    for i, (_, rec, st) in enumerate(columns):
        cx = i + 1
        if st.avg is not None and st.sd is not None:
            lo, hi = v_out(st.avg - st.sd, units), v_out(st.avg + st.sd, units)
            out.append(f'<rect x="{f.x(cx - half):.1f}" y="{f.y(hi):.1f}" width="{f.x(cx + half) - f.x(cx - half):.1f}" '
                       f'height="{f.y(lo) - f.y(hi):.1f}" fill="{p["band"]}" opacity="0.16"/>')
        if st.avg is not None:
            a = v_out(st.avg, units)
            means.append((cx, a))
            out.append(f'<line x1="{f.x(cx - half):.1f}" y1="{f.y(a):.1f}" x2="{f.x(cx + half):.1f}" y2="{f.y(a):.1f}" '
                       f'stroke="{p["sel"]}" stroke-width="2.5"/>')
        for k, s in enumerate(rec.shots):
            x, y = f.x(cx + jit[k % len(jit)]), f.y(v_out(s.v0_ms, units))
            t = f"{i18n.t(lang, 'shot')} {s.number}: {fmt(v_out(s.v0_ms, units), 1, lang)} {un['v']}"
            if s.excluded:
                out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="none" stroke="{p["excl"]}" stroke-width="1.5"><title>{escape(t)}</title></circle>')
            else:
                out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{p["line"]}"><title>{escape(t)}</title></circle>')
    fit = linear_fit([m[0] for m in means], [m[1] for m in means]) if trend else None
    if fit:
        slope, icpt = fit
        x0, x1 = 0.6, n + 0.4
        out.append(f'<line x1="{f.x(x0):.1f}" y1="{f.y(slope * x0 + icpt):.1f}" x2="{f.x(x1):.1f}" y2="{f.y(slope * x1 + icpt):.1f}" '
                   f'stroke="{p["fg"]}" stroke-width="2" stroke-dasharray="8 5"/>')
        label = f"{i18n.t(lang, 'trend')} {'+' if slope >= 0 else '−'}{fmt(abs(slope), 1, lang)} {un['v']} {i18n.t(lang, 'trend_per_series')}"
        out.append(f'<text x="{W - MR}" y="{MT + 10}" fill="{p["fg"]}" font-size="11" text-anchor="end">{escape(label)}</text>')
    return _svg("".join(out), p, i18n.t(lang, "aria_strip"), theme)


def ladder_chart(points: list[dict], *, xlabel: str, units: str = "si", lang: str = "de",
                 theme: str = "dark") -> str:
    """V0-Mittelwert mit ±1 SD über dem variierten Wert (Pulvermenge oder Setztiefe)."""
    p, un = PALETTES[theme], unit_names(units)
    pts = sorted((q for q in points if q.get("x") is not None and q.get("avg") is not None), key=lambda q: q["x"])
    if not pts:
        return _empty(lang, theme)
    xs = [q["x"] for q in pts]
    lows = [v_out(q["avg"] - (q["sd"] or 0), units) for q in pts]
    highs = [v_out(q["avg"] + (q["sd"] or 0), units) for q in pts]
    pad = (max(xs) - min(xs)) * 0.06 or 0.5
    f = _Frame(min(xs) - pad, max(xs) + pad, min(lows), max(highs), p, lang, xlabel, f"V0 ({un['v']})")
    out = [f.axes()]
    out.append("".join(
        f'<line x1="{f.x(q["x"]):.1f}" y1="{f.y(hi):.1f}" x2="{f.x(q["x"]):.1f}" y2="{f.y(lo):.1f}" stroke="{p["excl"]}" stroke-width="2"/>'
        for q, lo, hi in zip(pts, lows, highs, strict=True)))
    if len(pts) > 1:
        coords = " ".join(f"{f.x(q['x']):.1f},{f.y(v_out(q['avg'], units)):.1f}" for q in pts)
        out.append(f'<polyline points="{coords}" fill="none" stroke="{p["line"]}" stroke-width="2"/>')
    for q in pts:
        t = f"{q.get('label', '')} Ø {fmt(v_out(q['avg'], units), 1, lang)} {un['v']} (n={q.get('n', '')})"
        out.append(f'<circle cx="{f.x(q["x"]):.1f}" cy="{f.y(v_out(q["avg"], units)):.1f}" r="5" fill="{p["sel"]}"><title>{escape(t)}</title></circle>')
    return _svg("".join(out), p, i18n.t(lang, "aria_ladder"), theme)
