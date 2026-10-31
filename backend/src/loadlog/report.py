"""HTML-Berichte (und daraus PDF per WeasyPrint) für Serie, Laborierung und Vergleich."""

from datetime import datetime

from jinja2 import Environment, select_autoescape

from . import charts, i18n
from .ballistics import series_bc
from .db import SeriesRecord
from .stats import Stats, compute
from .units import e_out, fmt, unit_names, v_out

_env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))

_CSS = """
@page { size: A4; margin: 18mm 15mm 16mm; @bottom-center { content: "LoadLog · " counter(page) " / " counter(pages); font-size: 8pt; color: #666; } }
body { font-family: 'IBM Plex Sans', 'DejaVu Sans', Arial, sans-serif; font-size: 10pt; color: #111820; }
h1 { font-size: 18pt; margin: 0 0 2mm; } h2 { font-size: 12pt; margin: 6mm 0 2mm; border-bottom: 1px solid #c9d1db; padding-bottom: 1mm; }
.meta { color: #4a5563; font-size: 9pt; margin-bottom: 4mm; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin: 2mm 0; }
th { text-align: left; color: #4a5563; font-weight: 600; border-bottom: 1px solid #8a96a5; padding: 1mm 2mm; }
td { padding: 1mm 2mm; border-bottom: 1px solid #e3e8ee; } td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
tr.ex td { color: #8a96a5; text-decoration: line-through; }
.kv { width: auto; } .kv th { width: 38mm; border: 0; padding: 0.5mm 2mm 0.5mm 0; } .kv td { border: 0; padding: 0.5mm 0; }
.cards { display: flex; gap: 3mm; margin: 2mm 0; } .card { border: 1px solid #c9d1db; border-radius: 2mm; padding: 2mm 3mm; flex: 1; }
.card .l { font-size: 8pt; color: #4a5563; } .card .v { font-size: 12pt; font-weight: 600; white-space: nowrap; }
figure { margin: 3mm 0; page-break-inside: avoid; } figure svg { width: 100%; height: auto; }
.legend { font-size: 8pt; color: #4a5563; } section { page-break-inside: auto; }
.disclaimer { margin-top: 8mm; padding: 2mm 3mm; border: 1px solid #c9d1db; border-left: 1mm solid #a35f00; font-size: 8pt; color: #4a5563; page-break-inside: avoid; }
"""

_BASE = """<!doctype html><html lang="{{ lang }}"><head><meta charset="utf-8"><title>{{ title }}</title>
<style>{{ css }}</style></head><body>
<h1>{{ title }}</h1><div class="meta">{{ subtitle }} · {{ T.created }}: {{ now }}</div>
{{ body|safe }}
<p class="disclaimer">{{ T.disclaimer }}</p></body></html>"""

_STATS = """<div class="cards">
<div class="card"><div class="l">{{ T.avg }}</div><div class="v">{{ s.avg }}</div><div class="l">{{ u.v }}</div></div>
<div class="card"><div class="l">{{ T.sd }}</div><div class="v">{{ s.sd }}</div><div class="l">{{ u.v }}</div></div>
<div class="card"><div class="l">{{ T.es }}</div><div class="v">{{ s.es }}</div><div class="l">{{ u.v }}</div></div>
<div class="card"><div class="l">{{ T.minmax }}</div><div class="v">{{ s.min }}–{{ s.max }}</div><div class="l">{{ u.v }}</div></div>
<div class="card"><div class="l">{{ T.energy }}</div><div class="v">{{ s.energy }}</div><div class="l">{{ u.e }} · {{ s.n }}/{{ s.total }} {{ T.counted }}</div></div>
<div class="card"><div class="l">{{ T.impulse }}</div><div class="v">{{ s.impulse }}</div><div class="l">{{ T.impulse_min }} {{ s.impulse_min }}</div></div></div>"""


def _stats_ctx(st: Stats, total: int, units: str, lang: str) -> dict:
    return {
        "avg": fmt(v_out(st.avg, units) if st.avg is not None else None, 1, lang),
        "sd": fmt(v_out(st.sd, units) if st.sd is not None else None, 1, lang),
        "es": fmt(v_out(st.es, units) if st.es is not None else None, 1, lang),
        "min": fmt(v_out(st.vmin, units) if st.vmin is not None else None, 1, lang),
        "max": fmt(v_out(st.vmax, units) if st.vmax is not None else None, 1, lang),
        "energy": fmt(e_out(st.energy_avg_j, units) if st.energy_avg_j is not None else None, 0, lang),
        "impulse": fmt(st.mip_avg, 0, lang),
        "impulse_min": fmt(st.mip_min, 0, lang),
        "n": st.n, "total": total,
    }


def _stats_html(st: Stats, total: int, units: str, lang: str) -> str:
    tpl = _env.from_string(_STATS)
    return tpl.render(T=i18n.TEXTS[lang], u=unit_names(units), s=_stats_ctx(st, total, units, lang))


def _wrap(title: str, subtitle: str, body: str, lang: str) -> str:
    return _env.from_string(_BASE).render(
        lang=lang, title=title, subtitle=subtitle, body=body, css=_CSS, T=i18n.TEXTS[lang],
        now=datetime.now().strftime("%d.%m.%Y %H:%M" if lang == "de" else "%d/%m/%Y %H:%M"),
    )


def _load_table(load: dict | None, weapon: dict | None, units: str, lang: str) -> str:
    if not load:
        return ""
    T = i18n.TEXTS[lang]
    gr = lambda x: f"{fmt(x, 1, lang)} gr" if x is not None else None  # noqa: E731
    mm = lambda x: f"{fmt(x, 2, lang)} mm" if x is not None else None  # noqa: E731
    rows = [
        (T["trial"], T[f"trial_{load['trial_type']}"]),
        (T["weapon"], " · ".join(str(x) for x in [(weapon or {}).get("name"), (weapon or {}).get("caliber"),
                                                  mm((weapon or {}).get("barrel_length_mm")), (weapon or {}).get("twist")] if x)),
        (T["powder"], " ".join(x for x in [load.get("powder_maker"), load.get("powder_name")] if x)),
        (T["lot"] + " (" + T["powder"] + ")", load.get("powder_lot")),
        (T["charge"], gr(load.get("charge_gr"))),
        (T["case"], " ".join(x for x in [load.get("case_maker")] if x)),
        (T["firings"], load.get("case_firings")), (T["trim"], mm(load.get("case_trim_mm"))),
        (T["primer"], load.get("primer")),
        (T["bullet"], " ".join(x for x in [load.get("bullet_maker"), load.get("bullet_type")] if x)),
        (T["bullet_weight"], gr(load.get("bullet_weight_gr"))), (T["lot"] + " (" + T["bullet"] + ")", load.get("bullet_lot")),
        (T["coal"], mm(load.get("coal_mm"))),
        (T["seating"], (mm(load.get("seating_depth_mm")) or "") + (f" ({load['seating_ref']})" if load.get("seating_ref") else "") or None),
        (T["crimp"], load.get("crimp")),
        (T["temperature"], f"{fmt(load['temperature_c'], 0, lang)} °C" if load.get("temperature_c") is not None else None),
        (T["notes"], load.get("notes")),
    ]
    rows = [(k, v) for k, v in rows if v not in (None, "")]
    tpl = _env.from_string('<h2>{{ T.head_data }}</h2><table class="kv">{% for k, v in rows %}<tr><th>{{ k }}</th><td>{{ v }}</td></tr>{% endfor %}</table>')
    return tpl.render(T=T, rows=rows)


def date_range(shots, lang: str) -> str:
    """Datum der Schüsse: ein Datum, bei mehreren Tagen "von – bis"."""
    days = sorted({s.taken_at.date() for s in shots})
    if not days:
        return "–"
    f = (lambda d: d.strftime("%d.%m.%Y")) if lang == "de" else (lambda d: d.strftime("%d/%m/%Y"))
    return f(days[0]) if len(days) == 1 else f"{f(days[0])} – {f(days[-1])}"


def series_label(rec: SeriesRecord, T: dict) -> str:
    return rec.name or f"{T['series']} {rec.number}"


def series_report(rec: SeriesRecord, load: dict | None = None, weapon: dict | None = None, *,
                  units: str = "si", lang: str = "de") -> str:
    T, u = i18n.TEXTS[lang], unit_names(units)
    st = compute(rec.shots)
    svg = charts.track_chart(rec, units=units, lang=lang, theme="light")
    shots = [{
        "n": s.number, "v0": fmt(v_out(s.v0_ms, units), 1, lang), "e": fmt(e_out(s.energy0_j, units), 0, lang),
        "p": fmt(s.mip, 0, lang),
        "sig": f"{s.signal_strength}/5" if s.signal_strength else "–", "time": s.taken_at.strftime("%H:%M:%S"),
        "ex": s.excluded,
    } for s in rec.shots]
    table = _env.from_string(
        '<h2>{{ T.shots }}</h2><table><tr><th>#</th><th class="n">V0 ({{ u.v }})</th><th class="n">E ({{ u.e }})</th><th class="n">{{ T.impulse_col }}</th>'
        '<th class="n">{{ T.signal }}</th><th>{{ T.time }}</th><th>{{ T.status }}</th></tr>'
        '{% for s in shots %}<tr class="{{ "ex" if s.ex else "" }}"><td>{{ s.n }}</td><td class="n">{{ s.v0 }}</td>'
        '<td class="n">{{ s.e }}</td><td class="n">{{ s.p }}</td><td class="n">{{ s.sig }}</td><td>{{ s.time }}</td>'
        '<td>{{ T.excluded if s.ex else T.included }}</td></tr>{% endfor %}</table>'
    ).render(T=T, u=u, shots=shots)
    bc = series_bc(rec.shots)
    bc_html = ""
    if bc["g1"]["avg"] is not None or bc["g7"]["avg"] is not None:
        parts = [f"{m.upper()}: {fmt(bc[m]['avg'], 3, lang)}" + (f" ± {fmt(bc[m]['sd'], 3, lang)}" if bc[m]["sd"] is not None else "")
                 + f" ({bc[m]['n']})" for m in ("g1", "g7") if bc[m]["avg"] is not None]
        bc_html = _env.from_string('<p class="meta"><strong>{{ T.bc }}</strong> {{ v }}<br>{{ T.bc_note }}</p>').render(T=T, v=" · ".join(parts))
    extra = ""
    if rec.note:
        extra = _env.from_string("<h2>{{ T.note }}</h2><p>{{ n }}</p>").render(T=T, n=rec.note)
    bits = []
    if rec.charge_gr is not None:
        bits.append(f"{T['charge']}: {fmt(rec.charge_gr, 1, lang)} gr")
    if rec.seating_depth_mm is not None:
        bits.append(f"{T['seating']}: {fmt(rec.seating_depth_mm, 2, lang)} mm")
    if rec.group_text:
        bits.append(f"{T['group']}: {rec.group_text}")
    if bits:
        extra = _env.from_string('<p class="meta">{{ b }}</p>').render(b=" · ".join(bits)) + extra  # Autoescape: freier Text
    body = (_load_table(load, weapon, units, lang) + extra + "<h2>" + T["avg"] + "</h2>"
            + _stats_html(st, len(rec.shots), units, lang) + bc_html
            + f'<figure>{svg}<div class="legend">{T["track_title"]}</div></figure>' + table)
    sub = series_label(rec, T) + (f" · {load['name']}" if load else "") + f" · {date_range(rec.shots, lang)}"
    return _wrap(T["report_series"], sub, body, lang)


def ladder_points(recs: list[SeriesRecord], by: str) -> list[dict]:
    pts = []
    for r in recs:
        x = r.charge_gr if by == "charge" else r.seating_depth_mm
        st = compute(r.shots)
        if x is not None and st.avg is not None:
            pts.append({"x": x, "avg": st.avg, "sd": st.sd, "n": st.n, "label": f"S{r.number}"})
    return pts


def _compare_table(recs: list[SeriesRecord], units: str, lang: str) -> str:
    T, u = i18n.TEXTS[lang], unit_names(units)
    rows, prev = [], None
    for r in recs:
        st = compute(r.shots)
        delta = None if prev is None or st.avg is None else v_out(st.avg, units) - v_out(prev, units)
        prev = st.avg if st.avg is not None else prev
        rows.append({
            "name": series_label(r, T), "n": f"{st.n}/{len(r.shots)}",
            "charge": fmt(r.charge_gr, 1, lang) if r.charge_gr is not None else "–",
            "seat": fmt(r.seating_depth_mm, 2, lang) if r.seating_depth_mm is not None else "–",
            **{k: v for k, v in _stats_ctx(st, len(r.shots), units, lang).items() if k in ("avg", "sd", "es")},
            "delta": "–" if delta is None else ("+" if delta >= 0 else "−") + fmt(abs(delta), 1, lang),
        })
    return _env.from_string(
        '<table><tr><th></th><th class="n">{{ T.shots }}</th><th class="n">{{ T.charge }} (gr)</th><th class="n">{{ T.seating }} (mm)</th>'
        '<th class="n">Ø ({{ u.v }})</th><th class="n">SD</th><th class="n">ES</th><th class="n">{{ T.delta_avg }}</th></tr>'
        '{% for r in rows %}<tr><td>{{ r.name }}</td><td class="n">{{ r.n }}</td><td class="n">{{ r.charge }}</td><td class="n">{{ r.seat }}</td>'
        '<td class="n">{{ r.avg }}</td><td class="n">{{ r.sd }}</td><td class="n">{{ r.es }}</td><td class="n">{{ r.delta }}</td></tr>{% endfor %}</table>'
    ).render(T=T, u=u, rows=rows)


def compare_report(recs: list[SeriesRecord], *, units: str = "si", lang: str = "de", title: str | None = None,
                   load: dict | None = None, weapon: dict | None = None) -> str:
    T = i18n.TEXTS[lang]
    cols = [(series_label(r, T), r, compute(r.shots)) for r in recs]
    body = _load_table(load, weapon, units, lang)
    body += f"<h2>{T['compare_title']}</h2><figure>{charts.strip_chart(cols, units=units, lang=lang, theme='light')}</figure>"
    for by, key in (("charge", "charge"), ("seating", "seating")):
        pts = ladder_points(recs, by)
        if len({q["x"] for q in pts}) >= 2:
            lab = f"{T[key]} ({'gr' if by == 'charge' else 'mm'})"
            body += (f"<h2>{T['ladder_title']} {T[key]}</h2><figure>"
                     f"{charts.ladder_chart(pts, xlabel=lab, units=units, lang=lang, theme='light')}</figure>")
    body += _compare_table(recs, units, lang)
    sub = (load["name"] + " · " if load else "") + f"{len(recs)} {T['series_pl']}"
    return _wrap(title or (T["report_load"] if load else T["report_compare"]), sub, body, lang)


def html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML  # lazy: braucht Pango

    # Berichte sind in sich geschlossen: nichts von Platte oder aus dem Netz laden (zweite Schutzschicht neben dem Escaping)
    try:
        from weasyprint.urls import URLFetcher

        fetcher = URLFetcher(allowed_protocols={"data"})
    except ImportError:  # WeasyPrint vor 68: Funktion statt Klasse
        from weasyprint import default_url_fetcher

        def fetcher(url: str, *args, **kwargs):
            if not url.startswith("data:"):
                raise ValueError(f"Ressource nicht erlaubt: {url[:40]}")
            return default_url_fetcher(url, *args, **kwargs)

    return HTML(string=html, url_fetcher=fetcher).write_pdf()


def pdf_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True
