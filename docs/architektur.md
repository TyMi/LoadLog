# Architektur

Ein Container: FastAPI-Backend (Python ≥ 3.12, im Container 3.15) liefert REST-API, serverseitig erzeugte
SVG-Diagramme, PDF-Berichte, CSV-Export, das gebaute Frontend (`/`) und das Handbuch (`/manual/<Version>/`).
Daten: eine SQLite-Datei im Volume `/data`.

## Datenmodell

`weapons` · `loads` (Laborierung: Stammdaten, Versuchsart single/ladder/seating) ·
`series` (importiert, eigener Name, Pulvermenge/Setztiefe, Trigger-Modus, Notiz, optionales Überschreib-Gewicht) ·
`series_loads` (n:m: eine Serie kann in mehreren Laborierungen liegen; ohne Eintrag = nicht zugeordnet) ·
`shots` (V0, V/E je Distanz als JSON, Signalstärke, `excluded`, Track als JSON). Alles in SI (m/s, m, J, g);
Umrechnung nur bei der Anzeige. Schema-Version in `PRAGMA user_version` (aktuell 4), Migrationen in `Database._migrate`;
`series.load_id` ist nur noch Altlast aus Schema ≤ 3.
Duplikate: `source_key = Geräte-ID:Serien-Nr:erster Zeitstempel`, zusätzlich Abgleich über erster Schuss (±2 s), Schusszahl und V0
(SD-Karte nach GRT wertet auf, GRT nach SD wird übersprungen). Löschen einer Laborierung entfernt nur die Verknüpfungen,
Löschen einer Serie löscht ihre Schüsse. Import einer Quelle: eine Transaktion (`Database.import_batch`).

## Entscheidungen

- **PDF im Container** (WeasyPrint, HTML+SVG, Seitenzahl per CSS): gleiches Aussehen auf allen
  Geräten, DE/EN und Einheiten wie in der Oberfläche; Druckansicht (`format=html`) als Fallback.
- **Diagramme nur serverseitig** (`charts.py`): eine Implementierung für Oberfläche (dunkel) und
  PDF (hell); das Frontend lädt SVG per `fetch` und setzt es inline ein (Tooltips via `<title>`).
- **Statistik serverseitig** (`stats.py`, ohne ausgeschlossene Schüsse, SD mit n−1), dazu Impuls (MIP) und BC (`ballistics.py`,
  nur in der Serienansicht, nicht zwischengespeichert).
- **Meldungen mit Code** (`messages.py`): Server liefert `{code, message, params}`, die Oberfläche übersetzt DE/EN.
- **Sicherung** über die SQLite-Backup-API; Wiederherstellen prüft die Datei (Integrität, Tabellen, keine Trigger/Views, Schema nicht neuer;
  nach der Migration Fremdschlüssel und JSON-Spalten), legt den alten Stand unter `backups/` ab und hebt ältere Sicherungen per Migration an.
  Es bleiben die neuesten N Sicherheitskopien (Einstellung `backup_keep`, Standard 5, in `settings.json` neben der Datenbank, in der Oberfläche
  unter Einstellungen). `LOADLOG_ALLOW_RESTORE=0` schaltet das Wiederherstellen ab.
- **Version** dreistufig, Handbuch unter `/manual/<Major.Minor>/`.
- **Ladeleitern/Setztiefen** sind nur Darstellung: V0-Ø ± SD über Pulvermenge bzw. Setztiefe der Serien.
- **Kein Login**; Container bindet standardmäßig an 127.0.0.1, läuft als Nicht-root, read-only,
  ohne Capabilities. Uploads ≤ 50 MB (GRT ≤ 10 MB, Sicherungen ≤ 200 MB, vorab per Anfragegröße geprüft), ZIP nur im Speicher gelesen.
  Schreibende Anfragen von fremden Webseiten (`Sec-Fetch-Site`, `Origin`) werden abgewiesen, optional `LOADLOG_ALLOWED_HOSTS` gegen DNS-Rebinding
  (ohne die Einstellung warnt der Start bei Bindung an das Netz). API-Antworten tragen `Cache-Control: no-store`. Compose begrenzt Speicher und Prozesse.
- **GRT-Import** (`grt.py`, Format in `grt-format.md`): legt Laborierung und Serien an; DOCTYPE/ENTITY werden abgelehnt.
- **Import**: `.lbr` bevorzugt (volle Genauigkeit, Signalstärke), sonst `Report.csv`; Tracks aus
  `TRK/Shot…Track.csv`; Geräteeinheiten aus dem Report-Kopf (fps/yd werden umgerechnet,
  bisher nur mit synthetischen Imperial-Daten getestet).

## API

Vollständige Liste; die maschinenlesbare Fassung liefert `/api/openapi.json` (Oberfläche unter `/api/docs`). Alle Antworten unter `/api/`
tragen `Cache-Control: no-store`. `lang` ist `de|en`, `units` ist `si|imp`, `theme` ist `dark` oder `light`.
Fehler: `{"detail": {"code", "message", "params"}}` (Meldungscodes in `messages.py`, Übersetzungen in `frontend/src/i18n.ts`).

| Bereich | Aufruf | Zweck |
|---|---|---|
| Allgemein | `GET /api/health` | Status, Version, Handbuchversion, PDF verfügbar |
| Einstellungen | `GET/PATCH /api/settings` | Zahl der Sicherheitskopien (`backup_keep`, 1 bis 100) |
| Waffen | `GET/POST /api/weapons`, `PUT/DELETE /api/weapons/{id}` | Waffen verwalten |
| Laborierungen | `GET/POST /api/loads`, `GET/PUT/DELETE /api/loads/{id}` | Laborierungen verwalten |
| | `POST /api/loads/{id}/apply-weight[?clear=true]` | Geschossgewicht auf alle Serien anwenden oder die Überschreibung entfernen |
| | `GET /api/loads/{id}/ladder?by=charge\|seating` | Datenpunkte der Ladeleiter bzw. des Setztiefen-Tests |
| Import | `POST /api/import[?load_id=&assign_existing=true]` | SD-Karten-ZIP oder GRT-Datei (Multipart-Feld `file`); `assign_existing` legt bereits vorhandene Serien zusätzlich in die Laborierung |
| Serien | `GET /api/series[?unassigned=true&load_id=]` | Liste mit Filter (nicht zugeordnet, einer Laborierung) |
| | `GET/PATCH/DELETE /api/series/{id}` | Serie mit Schüssen, Laborierungen und BC lesen, ändern, löschen |
| | `PUT/DELETE /api/series/{id}/loads/{lid}` | Mehrfachzuordnung: Serie zusätzlich in eine Laborierung legen oder herausnehmen |
| | `PUT /api/series/{id}/shots/{n}/excluded` | Schuss ausschließen oder wieder einbeziehen (liefert die ganze Serie) |
| | `GET /api/compare?ids=` | Kennzahlen und Trend mehrerer Serien (1 bis 60) |
| Diagramme (SVG) | `GET /api/charts/series/{id}.svg[?sel=]` | Geschwindigkeit über Distanz, optional mit hervorgehobenem Schuss |
| | `GET /api/charts/compare.svg?ids=[&trend=]` | Serienvergleich |
| | `GET /api/charts/ladder/{id}.svg?by=` | Ladeleiter bzw. Setztiefe |
| Berichte | `GET /api/reports/series/{id}`, `/api/reports/load/{id}`, `/api/reports/compare?ids=` | PDF oder HTML (`format=pdf\|html`), Serienbericht mit optionalem `load_id` |
| Export | `GET /api/export/series/{id}.csv`, `GET /api/export/load/{id}.csv` | CSV je Schuss, folgt `lang` und `units` |
| Sicherung | `GET /api/system/backup` | Konsistente Kopie der Datenbank |
| | `POST /api/system/restore` | Sicherung einspielen (Kopf `X-LoadLog-Confirm: restore`; abschaltbar mit `LOADLOG_ALLOW_RESTORE=0`) |
| Dokumentation | `GET /api/docs`, `GET /api/openapi.json` | Swagger-Oberfläche (lädt Skripte von einem CDN) und Schema |
| Handbuch, Oberfläche | `GET /manual/<Major.Minor>/<de\|en>/`, `GET /` | Statische Dateien; ältere Handbuchadressen leiten weiter |
