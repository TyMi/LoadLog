"""FastAPI-Anwendung: REST-API, Diagramme, PDF-Berichte, Auslieferung von Oberfläche und Handbuch."""

import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__, charts, export, i18n, report
from .ballistics import series_bc
from .db import Database, NotFound, SeriesRecord
from .grt import GrtError, looks_like_grt, parse_grtload
from .importer import ImportFailure, import_zip
from .messages import CodedError, Note, note_json
from .models import GRAMS_PER_GRAIN
from .settings import LIMITS, Settings
from .stats import compute, linear_fit
from .units import check_units

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_RESTORE_BYTES = 200 * 1024 * 1024
MAX_COMPARE = 60
MAX_ID = 2**63 - 1  # größere Zahlen kann SQLite nicht speichern

_Str = Field(default=None, max_length=200)


class _Body(BaseModel):
    """Basis der Eingabemodelle: Leerraum am Rand wird entfernt, NaN/Infinity abgelehnt."""

    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)


def _not_null(v):
    if v is None:
        raise ValueError("darf nicht leer (null) sein")
    return v


class WeaponIn(_Body):
    name: str = Field(min_length=1, max_length=200)
    caliber: str | None = _Str
    barrel_length_mm: float | None = Field(default=None, ge=0, le=2000)
    twist: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)


class WeaponPatch(WeaponIn):
    name: str | None = Field(default=None, min_length=1, max_length=200)

    _name_not_null = field_validator("name")(_not_null)


class LoadPatch(_Body):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    trial_type: Literal["single", "ladder", "seating"] | None = None
    weapon_id: int | None = None
    powder_maker: str | None = _Str
    powder_name: str | None = _Str
    powder_lot: str | None = _Str
    charge_gr: float | None = Field(default=None, ge=0, le=500)
    case_maker: str | None = _Str
    case_firings: int | None = Field(default=None, ge=0, le=1000)
    case_trim_mm: float | None = Field(default=None, ge=0, le=500)
    primer: str | None = _Str
    bullet_maker: str | None = _Str
    bullet_type: str | None = _Str
    bullet_weight_gr: float | None = Field(default=None, ge=0, le=2000)
    bullet_lot: str | None = _Str
    coal_mm: float | None = Field(default=None, ge=0, le=500)
    seating_depth_mm: float | None = Field(default=None, ge=-50, le=100)
    seating_ref: str | None = _Str
    crimp: str | None = _Str
    temperature_c: float | None = Field(default=None, ge=-60, le=80)
    notes: str | None = Field(default=None, max_length=4000)
    status: Literal["draft", "testing", "validated", "retired"] | None = None  # leer = ohne Angabe (siehe LOAD_STATUS)

    _name_not_null = field_validator("name", "trial_type")(_not_null)


class LoadIn(LoadPatch):
    name: str = Field(min_length=1, max_length=200)


class SeriesPatch(_Body):
    load_id: int | None = None  # Kurzform: ersetzt die Zuordnung durch genau diese Laborierung (None = lösen)
    load_ids: list[int] | None = Field(default=None, max_length=200)  # ersetzt die Zuordnung durch diese Liste
    name: str | None = Field(default=None, max_length=200)
    weight_override_g: float | None = Field(default=None, ge=0.1, le=100)  # None = Messwert verwenden
    charge_gr: float | None = Field(default=None, ge=0, le=500)
    seating_depth_mm: float | None = Field(default=None, ge=-50, le=100)
    note: str | None = Field(default=None, max_length=4000)
    group_text: str | None = Field(default=None, max_length=200)  # Gruppengröße als freier Text
    trigger_mode: Literal["doppler", "internal", "external"] | None = None


class DuplicateIn(_Body):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class SettingsPatch(_Body):
    backup_keep: int | None = Field(default=None, ge=LIMITS["backup_keep"][0], le=LIMITS["backup_keep"][1])


class ExcludedIn(_Body):
    excluded: bool


def shot_json(s) -> dict:
    return {
        "number": s.number, "taken_at": s.taken_at.isoformat(), "weight_g": s.weight_g, "v0_ms": s.v0_ms,
        "energy0_j": s.energy0_j, "power_factor": s.power_factor, "signal_strength": s.signal_strength,
        "excluded": s.excluded, "distances_m": s.distances_m, "velocities_ms": s.velocities_ms,
        "energies_j": s.energies_j, "mip": s.mip,
    }


MANUAL_VERSION = ".".join(__version__.split(".")[:2])  # das Handbuch gilt für Major.Minor, nicht für jeden Patch-Stand


def fail(status: int, code: str, **params) -> HTTPException:
    """HTTP-Fehler mit Meldungscode, Parametern und deutschem Rückfalltext."""
    return HTTPException(status, detail=Note(code, **params).as_dict())


def coded(status: int, exc: CodedError) -> HTTPException:
    return HTTPException(status, detail=exc.note.as_dict())


def series_json(rec: SeriesRecord, with_shots: bool = False) -> dict:
    out = {
        "id": rec.id, "number": rec.number, "name": rec.name, "weight_override_g": rec.weight_override_g,
        "weight_measured_g": rec.measured_weight_g, "device_id": rec.device_id, "load_id": rec.load_id, "load_ids": rec.load_ids,
        "taken_at": rec.taken_at.isoformat() if rec.taken_at else None, "charge_gr": rec.charge_gr,
        "seating_depth_mm": rec.seating_depth_mm, "note": rec.note, "group_text": rec.group_text, "trigger_mode": rec.trigger_mode,
        "shots_total": len(rec.shots), "weight_g": rec.shots[0].weight_g if rec.shots else None,
        "stats": compute(rec.shots).as_dict(),
    }
    if with_shots:
        out["shots"] = [shot_json(s) for s in rec.shots]
        out["bc"] = series_bc(rec.shots)
    return out


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "report"


def exposure_warning(env: dict | None = None) -> str | None:
    """Hinweis für das Startprotokoll, wenn LoadLog im Netz erreichbar ist, ohne dass erlaubte Host-Namen gesetzt sind."""
    env = os.environ if env is None else env
    bind = env.get("LOADLOG_BIND") or env.get("LOADLOG_HOST") or "127.0.0.1"
    if bind in ("127.0.0.1", "localhost", "::1") or env.get("LOADLOG_ALLOWED_HOSTS", "").strip():
        return None
    return (f"LoadLog ist im Netz erreichbar (Bindung {bind}), aber LOADLOG_ALLOWED_HOSTS ist leer: Es gibt weder Anmeldung noch "
            "Prüfung des Host-Namens (Schutz vor DNS-Rebinding). Siehe Handbuch, Abschnitt \"Betrieb im Netz\".")


def _same_origin(origin: str, request: Request, allowed: list[str]) -> bool:
    """Gehört der `Origin`-Kopf zu dieser Anwendung? Verglichen wird mit dem Host der Anfrage, dem von einem Proxy gemeldeten
    Host und den erlaubten Host-Namen (mit oder ohne Port)."""
    host = urlsplit(origin).netloc.lower()
    if not host:
        return False
    names = {request.headers.get("host", "").lower(), request.headers.get("x-forwarded-host", "").lower(), *(a.lower() for a in allowed)}
    return host in names or host.rsplit(":", 1)[0] in {n for n in names if ":" not in n}


def create_app(db_path: str | Path | None = None, static_dir: str | Path | None = None,
               manual_dir: str | Path | None = None) -> FastAPI:
    data_dir = Path(os.environ.get("LOADLOG_DATA_DIR", "data"))
    db = Database(db_path if db_path is not None else data_dir / "loadlog.sqlite3")
    settings = Settings(None if db.path == ":memory:" else Path(db.path).parent / "settings.json")
    restore_allowed = os.environ.get("LOADLOG_ALLOW_RESTORE", "1").strip().lower() not in ("0", "false", "no", "off")
    app = FastAPI(title="LoadLog", version=__version__, docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    hosts = [h.strip() for h in os.environ.get("LOADLOG_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if hosts:  # optional: schützt vor DNS-Rebinding, wenn die App im Netz erreichbar ist
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = None
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            # Schreibende Anfragen, die der Browser von einer fremden Webseite aus schickt, werden abgewiesen (CSRF)
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") in ("cross-site", "same-site") or (origin is not None and not _same_origin(origin, request, hosts)):
                resp = JSONResponse({"detail": Note("cross_site_blocked").as_dict()}, status_code=403)
            else:  # zu große Uploads schon anhand von Content-Length ablehnen, bevor sie gelesen werden
                limit = {"/api/import": MAX_UPLOAD_BYTES, "/api/system/restore": MAX_RESTORE_BYTES}.get(request.url.path)
                length = request.headers.get("content-length", "")
                if limit and not length.isdigit():  # ohne Längenangabe (chunked) ließe sich die Grenze erst nach dem Einlesen prüfen
                    resp = JSONResponse({"detail": Note("length_required").as_dict()}, status_code=411)
                elif limit and int(length) > limit + 1024 * 1024:
                    resp = JSONResponse({"detail": Note("upload_too_large", max=limit // (1024 * 1024)).as_dict()}, status_code=413)
        resp = resp or await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")  # Daten nicht in Browser- oder Proxy-Zwischenspeichern ablegen
        if not request.url.path.startswith("/api/docs"):
            resp.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
            )
        return resp

    @app.exception_handler(OverflowError)  # ID größer als SQLite-Integer: gibt es sicher nicht
    async def too_large(_: Request, exc: OverflowError):
        return JSONResponse({"detail": Note("not_found", what="-").as_dict()}, status_code=404)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_: Request, exc: RequestValidationError):
        """Eingabefehler als übersetzbare Meldung; der Wert selbst wird nicht zurückgegeben (kann NaN enthalten)."""
        err = exc.errors()[0]
        field = ".".join(str(x) for x in err.get("loc", ()) if x not in ("body", "query", "path")) or "-"
        ctx = err.get("ctx", {})
        kind = err.get("type", "")
        if kind in ("greater_than_equal", "greater_than"):
            note = Note("value_min", field=field, limit=ctx.get("ge", ctx.get("gt")))
        elif kind in ("less_than_equal", "less_than"):
            note = Note("value_max", field=field, limit=ctx.get("le", ctx.get("lt")))
        elif kind.startswith(("string_too", "too_long", "too_short")):
            note = Note("value_length", field=field)
        else:
            note = Note("value_invalid", field=field)
        return JSONResponse({"detail": note.as_dict()}, status_code=422)

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound):
        return JSONResponse({"detail": Note("not_found", what=str(exc)).as_dict()}, status_code=404)

    def opts(lang: str, units: str, theme: str = "dark") -> tuple[str, str, str]:
        try:
            i18n.check_lang(lang)
            check_units(units)
        except ValueError as exc:
            raise coded(422, exc) from exc
        if theme not in charts.PALETTES:
            raise fail(422, "bad_theme")
        return lang, units, theme

    def parse_ids(ids: str) -> list[int]:
        try:
            out = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError as exc:
            raise fail(422, "ids_format") from exc
        if any(not 1 <= i <= MAX_ID for i in out):
            raise fail(422, "ids_invalid")
        if not out or len(out) > MAX_COMPARE:
            raise fail(422, "ids_count", max=MAX_COMPARE)
        return out

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__, "manual_version": MANUAL_VERSION, "pdf": report.pdf_available()}

    # ---- Waffen ----
    @app.get("/api/weapons")
    def weapons():
        return db.list_weapons()

    @app.post("/api/weapons", status_code=201)
    def create_weapon(body: WeaponIn):
        return db.get_weapon(db.create_weapon(body.model_dump(exclude_unset=True)))

    @app.put("/api/weapons/{wid}")
    def update_weapon(wid: int, body: WeaponPatch):
        db.update_weapon(wid, body.model_dump(exclude_unset=True))
        return db.get_weapon(wid)

    @app.delete("/api/weapons/{wid}", status_code=204)
    def delete_weapon(wid: int):
        db.delete_weapon(wid)

    # ---- Laborierungen ----
    def load_series(load_id: int) -> list[SeriesRecord]:
        return [db.get_series(i) for i in db.list_series_ids(load_id=load_id)]

    def load_summary(load: dict) -> dict:
        recs = load_series(load["id"])
        shots = [s for r in recs for s in r.shots]
        weapon = db.get_weapon(load["weapon_id"]) if load.get("weapon_id") else None
        return {**load, "weapon_name": weapon["name"] if weapon else None, "series_count": len(recs),
                "shots_total": len(shots), "stats": compute(shots).as_dict()}

    @app.get("/api/loads")
    def loads():
        return [load_summary(x) for x in db.list_loads()]

    @app.post("/api/loads", status_code=201)
    def create_load(body: LoadIn):
        data = body.model_dump(exclude_unset=True)
        if data.get("weapon_id") is not None:
            db.get_weapon(data["weapon_id"])
        return load_summary(db.get_load(db.create_load(data)))

    @app.get("/api/loads/{lid}")
    def get_load(lid: int):
        load = db.get_load(lid)
        weapon = db.get_weapon(load["weapon_id"]) if load.get("weapon_id") else None
        parent, variants = db.load_family(lid)
        return {**load_summary(load), "weapon": weapon, "parent": parent, "variants": variants,
                "series": [series_json(r) for r in load_series(lid)]}

    @app.put("/api/loads/{lid}")
    def update_load(lid: int, body: LoadPatch):
        data = body.model_dump(exclude_unset=True)
        if data.get("weapon_id") is not None:
            db.get_weapon(data["weapon_id"])
        db.update_load(lid, data)
        return load_summary(db.get_load(lid))

    @app.post("/api/loads/{lid}/duplicate", status_code=201)
    def duplicate_load(lid: int, body: DuplicateIn | None = None):
        """Neue Laborierung als Entwurf mit den Stammdaten der Vorlage (ohne Serien) und Verweis auf sie."""
        return load_summary(db.get_load(db.duplicate_load(lid, body.name if body else None)))

    @app.delete("/api/loads/{lid}", status_code=204)
    def delete_load(lid: int):
        db.delete_load(lid)

    @app.post("/api/loads/{lid}/apply-weight")
    def apply_weight(lid: int, clear: bool = False):
        """Geschossgewicht der Laborierung für MIP und Energie auf alle ihre Serien anwenden (oder wieder entfernen)."""
        load = db.get_load(lid)
        gr = load.get("bullet_weight_gr")
        if not clear and not gr:
            raise fail(400, "no_weight")
        grams = None if clear else round(gr * GRAMS_PER_GRAIN, 4)
        if grams is not None and not 0.1 <= grams <= 100:  # dieselbe Grenze wie beim Überschreiben einer einzelnen Serie
            raise fail(400, "weight_out_of_range")
        return {"series": db.set_weight_override_for_load(lid, grams), "weight_override_g": grams}

    @app.get("/api/loads/{lid}/ladder")
    def ladder(lid: int, by: Literal["charge", "seating"] = "charge"):
        db.get_load(lid)
        return report.ladder_points(load_series(lid), by)

    # ---- Import und Serien ----
    @app.post("/api/import")
    async def import_card(file: UploadFile, load_id: int | None = None, assign_existing: bool = False):
        if load_id is not None:
            db.get_load(load_id)  # 404, wenn die Laborierung fehlt
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data += chunk
            if len(data) > MAX_UPLOAD_BYTES:
                raise fail(413, "upload_too_large", max=MAX_UPLOAD_BYTES // (1024 * 1024))
        if looks_like_grt(bytes(data)):
            return import_grt(bytes(data), load_id, assign_existing)
        try:
            result = import_zip(bytes(data))
        except ImportFailure as exc:
            raise coded(400, exc) from exc
        events: list = []
        _, saved = db.import_batch(result.series, load_id=load_id, events=events, assign_existing=assign_existing)
        result.warnings.extend(dup_notes(events))
        return {
            "imported": [{"id": sid, "number": s.number} for (sid, new), s in zip(saved, result.series, strict=True) if new],
            "skipped": sum(1 for _, new in saved if not new),
            "assigned": sum(1 for e in events if e[0] == "assigned"),
            "warnings": [note_json(w) for w in result.warnings],
            "load_id": load_id,
        }

    def dup_notes(events: list) -> list[Note]:
        out = []
        for kind, s, existing in events:
            label = s.name or Note("series_label", no=s.number)
            code = {"upgraded": "upgraded_series", "assigned": "assigned_existing"}.get(kind, "duplicate_series")
            out.append(Note(code, label=label, id=existing))
        return out

    def import_grt(data: bytes, into_load: int | None, assign_existing: bool = False) -> dict:
        try:
            grt = parse_grtload(data)
        except GrtError as exc:
            raise coded(400, exc) from exc
        # eine Transaktion: neue Laborierung (nur ohne Ziel-Laborierung und nur, wenn es neue Serien gibt) und Serien
        events: list = []
        load_id, saved = db.import_batch(grt.series, load_data=None if into_load is not None else grt.load, load_id=into_load,
                                         events=events, assign_existing=assign_existing)
        grt.warnings.extend(dup_notes(events))
        if into_load is not None:  # leere Kopfdaten der Laborierung ergänzen, vorhandene nie überschreiben
            current = db.get_load(into_load)
            fill = {k: v for k, v in grt.load.items() if k not in ("name", "trial_type") and current.get(k) in (None, "")}
            if fill:
                db.update_load(into_load, fill)
        return {
            "imported": [{"id": sid, "number": s.number} for (sid, new), s in zip(saved, grt.series, strict=True) if new],
            "skipped": sum(1 for _, new in saved if not new),
            "assigned": sum(1 for e in events if e[0] == "assigned"),
            "warnings": [note_json(w) for w in grt.warnings],
            "load_id": load_id,
        }

    def series_detail(rec: SeriesRecord) -> dict:
        """Serie mit Schüssen und Laborierungen (Antwort von GET und von Änderungen an Schüssen)."""
        out = series_json(rec, with_shots=True)
        out["load"] = db.get_load(rec.load_id) if rec.load_id else None
        out["loads"] = [db.get_load(i) for i in rec.load_ids]
        return out

    @app.get("/api/series")
    def list_series(unassigned: bool = False, load_id: int | None = None):
        return [series_json(db.get_series(i)) for i in db.list_series_ids(load_id=load_id, unassigned=unassigned)]

    @app.get("/api/series/{sid}")
    def get_series(sid: int):
        rec = db.get_series(sid, with_track=True)  # der BC wird aus dem Track berechnet, nicht nur aus Dx1..Dx5
        return series_detail(rec)

    @app.patch("/api/series/{sid}")
    def patch_series(sid: int, body: SeriesPatch):
        data = body.model_dump(exclude_unset=True)
        if "name" in data and not data["name"]:
            data["name"] = None  # leerer Name = ohne Namen
        if "load_id" in data:
            lid = data.pop("load_id")
            data.setdefault("load_ids", [] if lid is None else [lid])
        if data.get("load_ids") is None:
            data.pop("load_ids", None)
        db.update_series(sid, data)
        return series_json(db.get_series(sid))

    @app.put("/api/series/{sid}/loads/{lid}")
    def add_to_load(sid: int, lid: int):
        """Serie zusätzlich in eine weitere Laborierung legen (sie kann in mehreren liegen)."""
        db.add_series_to_load(sid, lid)
        return series_json(db.get_series(sid))

    @app.delete("/api/series/{sid}/loads/{lid}")
    def remove_from_load(sid: int, lid: int):
        """Serie aus dieser Laborierung nehmen; die Serie bleibt erhalten."""
        db.remove_series_from_load(sid, lid)
        return series_json(db.get_series(sid))

    @app.delete("/api/series/{sid}", status_code=204)
    def delete_series(sid: int):
        db.delete_series(sid)

    @app.put("/api/series/{sid}/shots/{number}/excluded")
    def set_excluded(sid: int, number: int, body: ExcludedIn):
        db.set_shot_excluded(sid, number, body.excluded)
        return series_detail(db.get_series(sid, with_track=True))

    @app.get("/api/compare")
    def compare(ids: str):
        recs = [db.get_series(i) for i in parse_ids(ids)]
        means = [(i + 1, compute(r.shots).avg) for i, r in enumerate(recs)]
        fit = linear_fit([m[0] for m in means if m[1] is not None], [m[1] for m in means if m[1] is not None])
        return {"series": [series_json(r) for r in recs], "trend_ms_per_series": fit[0] if fit else None}

    # ---- Diagramme ----
    def svg(content: str) -> Response:
        return Response(content, media_type="image/svg+xml")

    @app.get("/api/charts/series/{sid}.svg")
    def chart_series(sid: int, sel: int | None = None, lang: str = "de", units: str = "si", theme: str = "dark"):
        lang, units, theme = opts(lang, units, theme)
        return svg(charts.track_chart(db.get_series(sid, with_track=True), selected=sel, units=units, lang=lang, theme=theme))

    @app.get("/api/charts/compare.svg")
    def chart_compare(ids: str, trend: bool = True, lang: str = "de", units: str = "si", theme: str = "dark"):
        lang, units, theme = opts(lang, units, theme)
        recs = [db.get_series(i) for i in parse_ids(ids)]
        cols = [(report.series_label(r, i18n.TEXTS[lang]), r, compute(r.shots)) for r in recs]
        return svg(charts.strip_chart(cols, trend=trend, units=units, lang=lang, theme=theme))

    @app.get("/api/charts/ladder/{lid}.svg")
    def chart_ladder(lid: int, by: Literal["charge", "seating"] = "charge", lang: str = "de",
                     units: str = "si", theme: str = "dark"):
        lang, units, theme = opts(lang, units, theme)
        db.get_load(lid)
        label = f"{i18n.t(lang, 'charge' if by == 'charge' else 'seating')} ({'gr' if by == 'charge' else 'mm'})"
        return svg(charts.ladder_chart(report.ladder_points(load_series(lid), by), xlabel=label, units=units, lang=lang, theme=theme))

    # ---- Berichte ----
    def deliver(html: str, name: str, fmt: str) -> Response:
        if fmt == "html":
            return Response(html, media_type="text/html; charset=utf-8")
        if not report.pdf_available():
            raise fail(503, "pdf_unavailable")
        return Response(report.html_to_pdf(html), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{_slug(name)}.pdf"'})

    @app.get("/api/reports/series/{sid}")
    def report_series(sid: int, lang: str = "de", units: str = "si", format: Literal["pdf", "html"] = "pdf", load_id: int | None = None):
        lang, units, _ = opts(lang, units)
        rec = db.get_series(sid, with_track=True)
        ctx = load_id if load_id in rec.load_ids else rec.load_id  # Kopfdaten der gewählten (sonst ersten) Laborierung
        load = db.get_load(ctx) if ctx else None
        weapon = db.get_weapon(load["weapon_id"]) if load and load.get("weapon_id") else None
        return deliver(report.series_report(rec, load, weapon, units=units, lang=lang), f"loadlog-serie-{rec.number}", format)

    @app.get("/api/reports/load/{lid}")
    def report_load(lid: int, lang: str = "de", units: str = "si", format: Literal["pdf", "html"] = "pdf"):
        lang, units, _ = opts(lang, units)
        load = db.get_load(lid)
        weapon = db.get_weapon(load["weapon_id"]) if load.get("weapon_id") else None
        return deliver(report.compare_report(load_series(lid), units=units, lang=lang, load=load, weapon=weapon),
                       f"loadlog-{load['name']}", format)

    @app.get("/api/reports/compare")
    def report_compare(ids: str, lang: str = "de", units: str = "si", format: Literal["pdf", "html"] = "pdf"):
        lang, units, _ = opts(lang, units)
        recs = [db.get_series(i) for i in parse_ids(ids)]
        return deliver(report.compare_report(recs, units=units, lang=lang), "loadlog-vergleich", format)

    # ---- CSV-Export ----
    def csv_response(text: str, name: str) -> Response:
        return Response(text, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{_slug(name)}.csv"'})

    @app.get("/api/export/series/{sid}.csv")
    def export_series(sid: int, lang: str = "de", units: str = "si"):
        lang, units, _ = opts(lang, units)
        rec = db.get_series(sid)
        load = db.get_load(rec.load_id)["name"] if rec.load_id else None
        return csv_response(export.shots_csv([(load, rec)], units, lang), f"loadlog-serie-{rec.number}")

    @app.get("/api/export/load/{lid}.csv")
    def export_load(lid: int, lang: str = "de", units: str = "si"):
        lang, units, _ = opts(lang, units)
        load = db.get_load(lid)
        return csv_response(export.shots_csv([(load["name"], r) for r in load_series(lid)], units, lang), f"loadlog-{load['name']}")

    # ---- System: Sicherung und Wiederherstellung ----
    @app.get("/api/system/backup")
    def backup():
        """Konsistente Kopie der gesamten Datenbank zum Herunterladen."""
        fd, tmp = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        db.backup_to(tmp)
        name = f"loadlog-sicherung-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
        return FileResponse(tmp, media_type="application/vnd.sqlite3", filename=name, background=BackgroundTask(os.unlink, tmp))

    @app.post("/api/system/restore")
    async def restore(file: UploadFile, request: Request):
        """Ersetzt ALLE Daten durch eine Sicherung. Der Kopfwert verhindert, dass fremde Webseiten das auslösen können
        (ein Formular-Post ohne eigenen Kopf wird abgewiesen)."""
        if not restore_allowed:
            raise fail(403, "restore_disabled")
        if request.headers.get("x-loadlog-confirm") != "restore":
            raise fail(400, "restore_confirm")
        fd, tmp = tempfile.mkstemp(suffix=".sqlite3")
        try:
            size = 0
            with os.fdopen(fd, "wb") as out:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_RESTORE_BYTES:
                        raise fail(413, "upload_too_large", max=MAX_RESTORE_BYTES // (1024 * 1024))
                    out.write(chunk)
            try:
                return db.restore_from(tmp, keep=settings.get()["backup_keep"])
            except CodedError as exc:
                raise coded(400, exc) from exc
        finally:
            os.unlink(tmp)

    # ---- Papierkorb ----
    @app.get("/api/trash")
    def get_trash():
        return db.list_trash()

    @app.post("/api/trash/{kind}/{rid}/restore")
    def restore_trash(kind: Literal["series", "loads"], rid: int):
        db.restore_from_trash(kind, rid)
        return {"restored": kind, "id": rid}

    @app.delete("/api/trash/{kind}/{rid}")
    def purge_trash_entry(kind: Literal["series", "loads"], rid: int):
        return db.purge(kind, rid)

    @app.delete("/api/trash")
    def empty_trash():
        return db.purge()

    # ---- Einstellungen des Servers ----
    @app.get("/api/settings")
    def get_settings():
        return settings.get()

    @app.patch("/api/settings")
    def patch_settings(body: SettingsPatch):
        values = body.model_dump(exclude_none=True)
        out = settings.update(values) if values else settings.get()
        db.prune_safety_copies(out["backup_keep"])  # eine kleinere Zahl räumt sofort auf
        return out

    # ---- Handbuch und Oberfläche ----
    manual = Path(manual_dir or os.environ.get("LOADLOG_MANUAL_DIR", ""))
    if manual_dir or os.environ.get("LOADLOG_MANUAL_DIR"):
        if manual.is_dir():
            # Handbuch unter /manual/<Major.Minor>/<Sprache>/; ältere Adressen (/manual/de/) leiten dorthin weiter
            app.mount(f"/manual/{MANUAL_VERSION}", StaticFiles(directory=manual, html=True), name="manual")

            @app.api_route("/manual", methods=["GET", "HEAD"])
            @app.api_route("/manual/", methods=["GET", "HEAD"])
            @app.api_route("/manual/{lang}", methods=["GET", "HEAD"])
            @app.api_route("/manual/{lang}/", methods=["GET", "HEAD"])
            def manual_redirect(lang: str = ""):
                target = f"/manual/{MANUAL_VERSION}/{lang if lang in i18n.LANGS else ''}"
                return RedirectResponse(target.rstrip("/") + "/", status_code=307)
    static = Path(static_dir or os.environ.get("LOADLOG_STATIC_DIR", ""))
    if (static_dir or os.environ.get("LOADLOG_STATIC_DIR")) and static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="ui")
    return app
