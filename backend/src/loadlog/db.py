"""SQLite-Speicher: Waffen, Laborierungen, Serien, Schüsse."""

import json
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .messages import CodedError
from .models import Series, Shot, TrackPoint

SCHEMA_VERSION = 4

TRIAL_TYPES = ("single", "ladder", "seating")

WEAPON_FIELDS = ("name", "caliber", "barrel_length_mm", "twist", "notes")
LOAD_FIELDS = (
    "name", "trial_type", "weapon_id", "powder_maker", "powder_name", "powder_lot", "charge_gr",
    "case_maker", "case_firings", "case_trim_mm", "primer", "bullet_maker", "bullet_type",
    "bullet_weight_gr", "bullet_lot", "coal_mm", "seating_depth_mm", "seating_ref", "crimp",
    "temperature_c", "notes",
)
SERIES_FIELDS = ("name", "weight_override_g", "charge_gr", "seating_depth_mm", "note", "trigger_mode")

_SCHEMA = """
CREATE TABLE weapons (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, caliber TEXT, barrel_length_mm REAL,
  twist TEXT, notes TEXT
);
CREATE TABLE loads (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, trial_type TEXT NOT NULL DEFAULT 'single',
  weapon_id INTEGER REFERENCES weapons(id) ON DELETE SET NULL,
  powder_maker TEXT, powder_name TEXT, powder_lot TEXT, charge_gr REAL,
  case_maker TEXT, case_firings INTEGER, case_trim_mm REAL, primer TEXT,
  bullet_maker TEXT, bullet_type TEXT, bullet_weight_gr REAL, bullet_lot TEXT,
  coal_mm REAL, seating_depth_mm REAL, seating_ref TEXT, crimp TEXT,
  temperature_c REAL, notes TEXT, created_at TEXT NOT NULL
);
CREATE TABLE series (
  id INTEGER PRIMARY KEY,
  number INTEGER NOT NULL, name TEXT, weight_override_g REAL, device_id TEXT, source_key TEXT NOT NULL UNIQUE,
  charge_gr REAL, seating_depth_mm REAL, note TEXT, trigger_mode TEXT, imported_at TEXT NOT NULL
);
CREATE TABLE shots (
  id INTEGER PRIMARY KEY, series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  number INTEGER NOT NULL, taken_at TEXT NOT NULL, weight_g REAL, v0_ms REAL NOT NULL,
  distances_json TEXT, velocities_json TEXT, energy0_j REAL, energies_json TEXT,
  power_factor REAL, signal_strength INTEGER, excluded INTEGER NOT NULL DEFAULT 0,
  track_json TEXT, UNIQUE (series_id, number)
);
"""

_SERIES_LOADS = """
CREATE TABLE IF NOT EXISTS series_loads (
  series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  load_id INTEGER NOT NULL REFERENCES loads(id) ON DELETE CASCADE,
  PRIMARY KEY (series_id, load_id)
);
CREATE INDEX IF NOT EXISTS idx_series_loads_load ON series_loads(load_id);
"""
_SCHEMA += _SERIES_LOADS


class NotFound(LookupError):
    pass


@dataclass
class SeriesRecord:
    id: int
    load_ids: list[int]  # Laborierungen, in denen die Serie liegt (in Zuordnungsreihenfolge)
    number: int
    device_id: str | None
    charge_gr: float | None
    seating_depth_mm: float | None
    note: str | None
    trigger_mode: str | None
    imported_at: str
    shots: list[Shot] = field(default_factory=list)
    name: str | None = None  # frei vergebener Titel; leer = "Serie <Nr.>"
    weight_override_g: float | None = None  # überschreibt das am Gerät eingestellte Geschossgewicht (g)
    measured_weight_g: float | None = None  # Gewicht laut Messdatei, unverändert

    @property
    def load_id(self) -> int | None:
        """Erste (Haupt-)Laborierung; None = nicht zugeordnet."""
        return self.load_ids[0] if self.load_ids else None

    @property
    def taken_at(self) -> datetime | None:
        return min((s.taken_at for s in self.shots), default=None)


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory_conn: sqlite3.Connection | None = None
        with self.conn() as c:
            self._migrate(c)

    @staticmethod
    def _migrate(c: sqlite3.Connection) -> None:
        """Legt das Schema an oder hebt eine ältere Datenbank auf die aktuelle Version."""
        version = c.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            c.executescript(_SCHEMA)
            c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        elif version > SCHEMA_VERSION:
            raise RuntimeError(f"Datenbank-Schema {version} ist neuer als diese App")
        elif version < SCHEMA_VERSION:
            cols = {r[1] for r in c.execute("PRAGMA table_info(series)")}  # idempotent: nur ergänzen, was fehlt
            if version < 2 and "name" not in cols:
                c.execute("ALTER TABLE series ADD COLUMN name TEXT")
            if version < 3 and "weight_override_g" not in cols:
                c.execute("ALTER TABLE series ADD COLUMN weight_override_g REAL")
            if version < 4:  # eine Serie darf in mehreren Laborierungen liegen; series.load_id bleibt ungenutzt zurück
                c.executescript(_SERIES_LOADS)
                if "load_id" in cols:
                    c.execute("INSERT OR IGNORE INTO series_loads (series_id, load_id) SELECT id, load_id FROM series WHERE load_id IS NOT NULL")
            c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _schema_complete(c: sqlite3.Connection) -> bool:
        """Hat die Datenbank alle Tabellen und Spalten des aktuellen Schemas? (Schutz vor Sicherungen, deren Version nicht zum Inhalt passt)"""
        ref = sqlite3.connect(":memory:")
        try:
            ref.executescript(_SCHEMA)
            for (table,) in ref.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
                need = {r[1] for r in ref.execute(f"PRAGMA table_info({table})")}  # noqa: S608
                have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}  # noqa: S608
                if not need <= have:
                    return False
            return True
        finally:
            ref.close()

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        if self.path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
                self._memory_conn.execute("PRAGMA foreign_keys = ON")
            c = self._memory_conn
            try:
                yield c
                c.commit()
            except Exception:
                c.rollback()
                raise
            return
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    # ---- generische Stammdaten ----
    @staticmethod
    def _pick(data: dict, allowed: tuple[str, ...]) -> dict:
        return {k: data[k] for k in allowed if k in data}

    def _insert(self, table: str, values: dict) -> int:
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        with self.conn() as c:
            cur = c.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values()))  # noqa: S608
            return int(cur.lastrowid)

    def _update(self, table: str, row_id: int, values: dict) -> None:
        if not values:
            return
        sets = ", ".join(f"{k} = ?" for k in values)
        with self.conn() as c:
            cur = c.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*values.values(), row_id])  # noqa: S608
            if cur.rowcount == 0:
                raise NotFound(f"{table} {row_id}")

    def _get(self, table: str, row_id: int) -> dict:
        with self.conn() as c:
            row = c.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()  # noqa: S608
        if row is None:
            raise NotFound(f"{table} {row_id}")
        return dict(row)

    def _delete(self, table: str, row_id: int) -> None:
        with self.conn() as c:
            if c.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,)).rowcount == 0:  # noqa: S608
                raise NotFound(f"{table} {row_id}")

    # ---- Waffen ----
    def create_weapon(self, data: dict) -> int:
        return self._insert("weapons", self._pick(data, WEAPON_FIELDS))

    def update_weapon(self, weapon_id: int, data: dict) -> None:
        self._update("weapons", weapon_id, self._pick(data, WEAPON_FIELDS))

    def get_weapon(self, weapon_id: int) -> dict:
        return self._get("weapons", weapon_id)

    def delete_weapon(self, weapon_id: int) -> None:
        self._delete("weapons", weapon_id)

    def list_weapons(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM weapons ORDER BY name COLLATE NOCASE")]

    # ---- Laborierungen ----
    def create_load(self, data: dict) -> int:
        values = self._pick(data, LOAD_FIELDS)
        values["created_at"] = datetime.now().isoformat(timespec="seconds")
        return self._insert("loads", values)

    def update_load(self, load_id: int, data: dict) -> None:
        self._update("loads", load_id, self._pick(data, LOAD_FIELDS))

    def get_load(self, load_id: int) -> dict:
        return self._get("loads", load_id)

    def delete_load(self, load_id: int) -> None:
        self._delete("loads", load_id)

    def list_loads(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM loads ORDER BY name COLLATE NOCASE")]

    # ---- Serien und Schüsse ----
    @staticmethod
    def source_key(series: Series) -> str:
        first = min((s.taken_at for s in series.shots), default=None)
        return f"{series.device_id or 'unknown'}:{series.number:04d}:{first.isoformat() if first else ''}"

    def save_series(self, series: Series) -> tuple[int, bool]:
        """Speichert eine Serie. Rückgabe: (id, neu_angelegt). Bereits importierte werden übersprungen."""
        with self.conn() as c:
            return self._save_series(c, series, None)

    def import_batch(self, series: list[Series], load_data: dict | None = None, load_id: int | None = None,
                     events: list | None = None, assign_existing: bool = False) -> tuple[int | None, list[tuple[int, bool]]]:
        """Alles-oder-nichts-Import in EINER Transaktion: optional neue Laborierung (load_data) anlegen, alle neuen
        Serien dieser oder der übergebenen Laborierung zuordnen. Bei einem Fehler bleibt die Datenbank unverändert.
        `events` sammelt (art, serie, vorhandene_id) für erkannte Duplikate ("duplicate"), aufgewertete ("upgraded") und, mit
        `assign_existing`, bereits vorhandene Serien, die der Laborierung zugeordnet wurden ("assigned")."""
        with self.conn() as c:
            if load_id is not None and c.execute("SELECT 1 FROM loads WHERE id = ?", (load_id,)).fetchone() is None:
                raise NotFound(f"loads {load_id}")
            known = [c.execute("SELECT 1 FROM series WHERE source_key = ?", (self.source_key(s),)).fetchone() is not None
                     or self._match(c, s) is not None for s in series]
            if load_data is not None and load_id is None and (not series or not all(known)):  # ohne Serien: nur die Laborierung
                values = self._pick(load_data, LOAD_FIELDS)
                values["created_at"] = datetime.now().isoformat(timespec="seconds")
                cols, marks = ", ".join(values), ", ".join("?" for _ in values)
                load_id = int(c.execute(f"INSERT INTO loads ({cols}) VALUES ({marks})", list(values.values())).lastrowid)  # noqa: S608
            return load_id, [self._save_series(c, s, load_id, events, assign_existing) for s in series]

    # Toleranzen für "dieselbe Serie aus anderer Quelle" (SD-Karte und GRT-Datei): GRT rundet V0 auf 1 m/s
    DUP_SECONDS = 2
    DUP_V0_MS = 1.5

    def _match(self, c: sqlite3.Connection, series: Series) -> sqlite3.Row | None:
        """Bestehende Serie mit anderem Quellschlüssel, aber gleichen Messdaten (Zeitpunkt des ersten Schusses,
        Schusszahl und V0 aller Schüsse)."""
        if not series.shots:
            return None
        first = min(s.taken_at for s in series.shots)
        lo, hi = (first - timedelta(seconds=self.DUP_SECONDS)).isoformat(), (first + timedelta(seconds=self.DUP_SECONDS)).isoformat()
        cands = c.execute(
            "SELECT s.id, s.device_id FROM series s WHERE s.id IN (SELECT series_id FROM shots WHERE taken_at BETWEEN ? AND ?)"
            " AND (SELECT COUNT(*) FROM shots WHERE series_id = s.id) = ?", (lo, hi, len(series.shots))).fetchall()
        mine = [s.v0_ms for s in sorted(series.shots, key=lambda x: x.number)]
        for cand in cands:
            theirs = [r["v0_ms"] for r in c.execute("SELECT v0_ms FROM shots WHERE series_id = ? ORDER BY number", (cand["id"],))]
            if all(abs(a - b) <= self.DUP_V0_MS for a, b in zip(mine, theirs, strict=True)):
                return cand
        return None

    @staticmethod
    def _assign(c: sqlite3.Connection, series_id: int, load_id: int | None) -> bool:
        """Legt eine vorhandene Serie in die Laborierung; True, wenn sie dort noch nicht lag."""
        if load_id is None:
            return False
        return c.execute("INSERT OR IGNORE INTO series_loads (series_id, load_id) VALUES (?, ?)", (series_id, load_id)).rowcount > 0

    def _save_series(self, c: sqlite3.Connection, series: Series, load_id: int | None,
                     events: list | None = None, assign_existing: bool = False) -> tuple[int, bool]:
        key = self.source_key(series)
        row = c.execute("SELECT id FROM series WHERE source_key = ?", (key,)).fetchone()
        if row:
            if assign_existing and self._assign(c, int(row["id"]), load_id) and events is not None:
                events.append(("assigned", series, int(row["id"])))
            return int(row["id"]), False
        dup = self._match(c, series)
        if dup is not None:
            # SD-Karte nach GRT: die genaueren Messdaten ersetzen die gerundeten, Zuordnung und Eingaben bleiben
            upgrade = dup["device_id"] is None and series.device_id is not None
            if upgrade:
                self._upgrade(c, int(dup["id"]), series, key)
            assigned = assign_existing and self._assign(c, int(dup["id"]), load_id)
            if events is not None:
                if upgrade:
                    events.append(("upgraded", series, int(dup["id"])))
                if assigned:
                    events.append(("assigned", series, int(dup["id"])))
                elif not upgrade:
                    events.append(("duplicate", series, int(dup["id"])))
            return int(dup["id"]), False
        cur = c.execute(
            "INSERT INTO series (number, name, device_id, source_key, imported_at, charge_gr, note) VALUES (?,?,?,?,?,?,?)",
            (series.number, series.name, series.device_id, key, datetime.now().isoformat(timespec="seconds"),
             series.charge_gr, series.note),
        )
        sid = int(cur.lastrowid)
        self._insert_shots(c, sid, series, {})
        if load_id is not None:
            c.execute("INSERT INTO series_loads (series_id, load_id) VALUES (?, ?)", (sid, load_id))
        return sid, True

    @staticmethod
    def _insert_shots(c: sqlite3.Connection, sid: int, series: Series, excluded: dict[int, bool]) -> None:
        for i, s in enumerate(series.shots):
            track = [[p.time_s, p.velocity_ms, p.distance_m, p.snr] for p in s.track]
            c.execute(
                "INSERT INTO shots (series_id, number, taken_at, weight_g, v0_ms, distances_json,"
                " velocities_json, energy0_j, energies_json, power_factor, signal_strength, excluded,"
                " track_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, s.number, s.taken_at.isoformat(), s.weight_g, s.v0_ms,
                 json.dumps(s.distances_m), json.dumps(s.velocities_ms), s.energy0_j,
                 json.dumps(s.energies_j), s.power_factor, s.signal_strength, int(excluded.get(i, s.excluded)),
                 json.dumps(track) if track else None),
            )

    def _upgrade(self, c: sqlite3.Connection, sid: int, series: Series, key: str) -> None:
        old = [bool(r["excluded"]) for r in c.execute("SELECT excluded FROM shots WHERE series_id = ? ORDER BY number", (sid,))]
        c.execute("DELETE FROM shots WHERE series_id = ?", (sid,))
        c.execute("UPDATE series SET device_id = ?, source_key = ?, number = ? WHERE id = ?", (series.device_id, key, series.number, sid))
        self._insert_shots(c, sid, series, dict(enumerate(old)))

    @staticmethod
    def _shot(row: sqlite3.Row, with_track: bool) -> Shot:
        track = []
        if with_track and row["track_json"]:
            track = [TrackPoint(*p) for p in json.loads(row["track_json"])]
        return Shot(
            number=row["number"], taken_at=datetime.fromisoformat(row["taken_at"]),
            weight_g=row["weight_g"], v0_ms=row["v0_ms"],
            distances_m=json.loads(row["distances_json"] or "[]"),
            velocities_ms=json.loads(row["velocities_json"] or "[]"),
            energy0_j=row["energy0_j"], energies_j=json.loads(row["energies_json"] or "[]"),
            power_factor=row["power_factor"], signal_strength=row["signal_strength"],
            track=track, excluded=bool(row["excluded"]),
        )

    def get_series(self, series_id: int, with_track: bool = False) -> SeriesRecord:
        with self.conn() as c:
            row = c.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
            if row is None:
                raise NotFound(f"series {series_id}")
            shots = [self._shot(r, with_track) for r in
                     c.execute("SELECT * FROM shots WHERE series_id = ? ORDER BY number", (series_id,))]
            load_ids = [r["load_id"] for r in
                        c.execute("SELECT load_id FROM series_loads WHERE series_id = ? ORDER BY rowid", (series_id,))]
        measured = shots[0].weight_g if shots else None
        if row["weight_override_g"]:  # Gewicht und davon abhängige Energie neu rechnen; die Messdaten bleiben unverändert
            m = row["weight_override_g"] / 1000
            for s in shots:
                if s.power_factor is not None and s.weight_g:  # PF = Gewicht × Geschwindigkeit: mit dem Gewicht skalieren
                    s.power_factor *= row["weight_override_g"] / s.weight_g
                s.weight_g = row["weight_override_g"]
                s.energy0_j = 0.5 * m * s.v0_ms**2
                s.energies_j = [0.5 * m * v**2 for v in s.velocities_ms]
        return SeriesRecord(
            weight_override_g=row["weight_override_g"] or None, measured_weight_g=measured,
            id=row["id"], load_ids=load_ids, number=row["number"], device_id=row["device_id"],
            charge_gr=row["charge_gr"], seating_depth_mm=row["seating_depth_mm"], note=row["note"],
            trigger_mode=row["trigger_mode"], imported_at=row["imported_at"], shots=shots, name=row["name"],
        )

    def list_series_ids(self, load_id: int | None = None, unassigned: bool = False) -> list[int]:
        sql, args = "SELECT id FROM series", []
        if unassigned:
            sql += " WHERE NOT EXISTS (SELECT 1 FROM series_loads WHERE series_id = series.id)"
        elif load_id is not None:
            sql += " WHERE id IN (SELECT series_id FROM series_loads WHERE load_id = ?)"
            args.append(load_id)
        sql += " ORDER BY (SELECT MIN(taken_at) FROM shots WHERE series_id = series.id), number"
        with self.conn() as c:
            return [r["id"] for r in c.execute(sql, args)]

    def update_series(self, series_id: int, data: dict) -> None:
        """Ändert Felder der Serie; `load_ids` (Liste) ersetzt die Zuordnung zu Laborierungen."""
        values = self._pick(data, SERIES_FIELDS)
        load_ids = data.get("load_ids")
        with self.conn() as c:
            if values:
                sets = ", ".join(f"{k} = ?" for k in values)
                if c.execute(f"UPDATE series SET {sets} WHERE id = ?", [*values.values(), series_id]).rowcount == 0:  # noqa: S608
                    raise NotFound(f"series {series_id}")
            elif c.execute("SELECT 1 FROM series WHERE id = ?", (series_id,)).fetchone() is None:
                raise NotFound(f"series {series_id}")
            if load_ids is not None:
                wanted = list(dict.fromkeys(load_ids))
                for lid in wanted:
                    if c.execute("SELECT 1 FROM loads WHERE id = ?", (lid,)).fetchone() is None:
                        raise NotFound(f"loads {lid}")
                have = [r["load_id"] for r in c.execute("SELECT load_id FROM series_loads WHERE series_id = ?", (series_id,))]
                for lid in have:
                    if lid not in wanted:
                        c.execute("DELETE FROM series_loads WHERE series_id = ? AND load_id = ?", (series_id, lid))
                for lid in wanted:
                    if lid not in have:
                        c.execute("INSERT INTO series_loads (series_id, load_id) VALUES (?, ?)", (series_id, lid))

    def set_weight_override_for_load(self, load_id: int, weight_g: float | None) -> int:
        """Setzt (oder löscht mit None) das Überschreib-Gewicht aller Serien der Laborierung in einer Anweisung; liefert die Anzahl."""
        with self.conn() as c:
            if c.execute("SELECT 1 FROM loads WHERE id = ?", (load_id,)).fetchone() is None:
                raise NotFound(f"loads {load_id}")
            return c.execute("UPDATE series SET weight_override_g = ? WHERE id IN (SELECT series_id FROM series_loads WHERE load_id = ?)",
                             (weight_g, load_id)).rowcount

    def add_series_to_load(self, series_id: int, load_id: int) -> None:
        """Legt die Serie zusätzlich in die Laborierung (bestehende Zuordnungen bleiben; doppelt ist harmlos)."""
        with self.conn() as c:
            for table, rid in (("series", series_id), ("loads", load_id)):
                if c.execute(f"SELECT 1 FROM {table} WHERE id = ?", (rid,)).fetchone() is None:  # noqa: S608
                    raise NotFound(f"{table} {rid}")
            c.execute("INSERT OR IGNORE INTO series_loads (series_id, load_id) VALUES (?, ?)", (series_id, load_id))

    def remove_series_from_load(self, series_id: int, load_id: int) -> None:
        """Nimmt die Serie aus der Laborierung; die Serie selbst bleibt (ggf. unzugeordnet)."""
        with self.conn() as c:
            if c.execute("DELETE FROM series_loads WHERE series_id = ? AND load_id = ?", (series_id, load_id)).rowcount == 0:
                raise NotFound(f"series {series_id} in loads {load_id}")

    def delete_series(self, series_id: int) -> None:
        self._delete("series", series_id)

    def set_shot_excluded(self, series_id: int, shot_number: int, excluded: bool) -> None:
        with self.conn() as c:
            cur = c.execute(
                "UPDATE shots SET excluded = ? WHERE series_id = ? AND number = ?",
                (int(excluded), series_id, shot_number),
            )
            if cur.rowcount == 0:
                raise NotFound(f"shot {series_id}/{shot_number}")

    # ---- Sicherung ----
    def backup_to(self, target: str | Path) -> None:
        """Konsistente Kopie der Datenbank (auch während des Betriebs)."""
        dst = sqlite3.connect(str(target))
        try:
            with self.conn() as c:
                c.backup(dst)
        finally:
            dst.close()

    @staticmethod
    def check_backup(path: str | Path) -> int:
        """Prüft eine hochgeladene Sicherung und liefert deren Schema-Version. Wirft CodedError("backup_invalid"/"backup_too_new")."""
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise CodedError("backup_invalid") from exc
        try:
            try:
                version = con.execute("PRAGMA user_version").fetchone()[0]
                ok = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                names = {(r[0], r[1]) for r in con.execute("SELECT type, name FROM sqlite_master")}
            except sqlite3.Error as exc:
                raise CodedError("backup_invalid") from exc
            tables = {n for t, n in names if t == "table"}
            if not ok or not {"weapons", "loads", "series", "shots"} <= tables or any(t in ("trigger", "view") for t, _ in names):
                raise CodedError("backup_invalid")
            if version < 1:
                raise CodedError("backup_invalid")
            if version > SCHEMA_VERSION:
                raise CodedError("backup_too_new", version=version, supported=SCHEMA_VERSION)
            return int(version)
        finally:
            con.close()

    @staticmethod
    def _data_consistent(c: sqlite3.Connection) -> bool:
        """Fremdschlüssel stimmen und die JSON-Spalten der Schüsse sind gültige Listen (sonst fielen Leseabfragen dauerhaft aus)."""
        if c.execute("PRAGMA foreign_key_check").fetchone() is not None:
            return False
        for col in ("distances_json", "velocities_json", "energies_json", "track_json"):
            bad = c.execute(
                f"SELECT 1 FROM shots WHERE {col} IS NOT NULL AND "  # noqa: S608
                f"COALESCE(CASE WHEN json_valid({col}) THEN json_type({col}) END, '') <> 'array' LIMIT 1").fetchone()
            if bad is not None:
                return False
        return True

    SAFETY_PREFIX = "vor-wiederherstellung-"

    def prune_safety_copies(self, keep: int) -> int:
        """Behält die neuesten `keep` Sicherheitskopien unter backups/ und löscht ältere; liefert die Zahl der gelöschten."""
        if self.path == ":memory:":
            return 0
        folder = Path(self.path).parent / "backups"
        if not folder.is_dir():
            return 0
        old = sorted(folder.glob(f"{self.SAFETY_PREFIX}*.sqlite3"))[:-keep] if keep > 0 else []
        for f in old:
            f.unlink(missing_ok=True)
        return len(old)

    def restore_from(self, path: str | Path, keep: int = 5) -> dict:
        """Ersetzt den Inhalt durch die (zuvor geprüfte) Sicherung. Vorher wird der aktuelle Stand neben der Datenbank
        unter backups/ abgelegt. Ältere Sicherungen werden auf das aktuelle Schema gehoben."""
        self.check_backup(path)
        with tempfile.TemporaryDirectory() as tmp:
            # erst eine Arbeitskopie migrieren und vollständig prüfen; die laufende Datenbank bleibt bis dahin unberührt
            work = Path(tmp) / "work.sqlite3"
            shutil.copyfile(path, work)
            con = sqlite3.connect(work)
            try:
                self._migrate(con)
                con.commit()
                if not self._schema_complete(con) or not self._data_consistent(con):
                    raise CodedError("backup_invalid")
            except sqlite3.Error as exc:
                raise CodedError("backup_invalid") from exc
            finally:
                con.close()
            if self.path != ":memory:":
                safety = Path(self.path).parent / "backups"
                safety.mkdir(parents=True, exist_ok=True)
                target = safety / f"vor-wiederherstellung-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3"  # eindeutig auch bei zwei Aufrufen je Sekunde
                self.backup_to(target)
                self.prune_safety_copies(keep)
            src = sqlite3.connect(f"file:{work}?mode=ro", uri=True)
            try:
                with self.conn() as c:
                    src.backup(c)
            finally:
                src.close()
        with self.conn() as c:
            return {k: c.execute(f"SELECT COUNT(*) FROM {k}").fetchone()[0] for k in ("weapons", "loads", "series", "shots")}  # noqa: S608
