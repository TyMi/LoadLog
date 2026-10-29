# LoadLog

**[Deutsch](#deutsch)** · **[English](#english)**

---

## Deutsch

Laborierungs-**Journal** und Auswertung für Chronograph-Daten: importiert die SD-Karten-Daten eines **LabRadar**
(inoffiziell, nicht mit dem Hersteller verbunden) sowie GRT-Dateien (`.grtload`), ordnet Serien Laborierungen zu, schließt
Ausreißer aus und zeigt Statistik, Impuls, Ballistischen Koeffizienten, Geschwindigkeitsverläufe, Serienvergleiche, Ladeleitern
und Trends. Berichte als PDF, Export als CSV. Oberfläche und Handbuch auf Deutsch und Englisch.

### Abgrenzung: Journal, keine Laborierungsentwicklung

LoadLog **legt ab und wertet aus, was du selbst geladen und gemessen hast**. Es ist **kein Werkzeug zur Entwicklung von Laborierungen**:

- Es berechnet **keine Ladedaten** und macht **keine Ladeempfehlungen**: keine Pulvermengen, keine Start- oder Maximalladungen,
  keine „beste“ Ladung, keine Druck- oder Sicherheitsberechnung.
- Es ersetzt **keine Ladetabellen, Handbücher oder Vorgaben der Hersteller**.
- Alle Angaben zu Pulver, Menge, Geschoss, Setztiefe usw. sind **reine Eingaben von dir**. LoadLog prüft sie weder auf Plausibilität noch auf Sicherheit.
- Auswertungen (Mittelwert, Standardabweichung, Energie, Impuls, ballistischer Koeffizient u. a.) sind rechnerische Näherungen aus den Messwerten.
- Alle Beispieldaten in Handbuch, Screenshots und Demo (Pulver, Mengen, Geschossgewichte, Geschwindigkeiten) sind **fiktiv**, keine Ladedaten und dürfen **nicht nachgeladen oder nachgebaut** werden.

### Haftungsausschluss

**Wiederladen ist gefährlich.** Falsche oder unsachgemäße Ladungen können zu Überdruck, zur Zerstörung der Waffe, zu schweren
Verletzungen oder zum Tod führen. **Du als Wiederlader bist allein verantwortlich**: für deine Ladedaten (nur aus verlässlichen,
aktuellen Quellen der Hersteller), für deine Sorgfalt, für den sicheren Umgang mit Waffen und Munition und für die Einhaltung der
geltenden Gesetze und Vorschriften.

LoadLog wird **unentgeltlich, „wie besehen“ und ohne jede Gewährleistung** bereitgestellt (siehe [MIT-Lizenz](LICENSE)). Die Haftung für
Vorsatz und grobe Fahrlässigkeit, für die Verletzung von Leben, Körper oder Gesundheit und nach zwingenden gesetzlichen Vorschriften
(z. B. dem Produkthaftungsgesetz) **bleibt unberührt**. Im Übrigen haften die Autorinnen, Autoren und Mitwirkenden, soweit gesetzlich
zulässig, **nicht** für Schäden jeder Art, insbesondere Sach- und Folgeschäden, die aus der Nutzung oder Nichtnutzung der Software, aus
Fehlern, fehlerhaften Messwerten, Berechnungen oder Darstellungen oder aus Datenverlust entstehen. Verlasse dich bei
sicherheitsrelevanten Entscheidungen und bei Wettkampfwertungen **nie allein** auf LoadLog. Für Nutzerinnen und Nutzer, auf die deutsches Recht anwendbar ist, gilt diese Haftungsregelung anstelle des Gewährleistungs- und Haftungsausschlusses der englischsprachigen MIT-Lizenz, soweit beide voneinander abweichen. Dieser Text ist keine Rechtsberatung.

LabRadar und Gordon's Reloading Tool sind Marken bzw. Produkte ihrer jeweiligen Hersteller. LoadLog ist ein unabhängiges, inoffizielles
Projekt ohne Verbindung zu ihnen.

### Schnellstart

```bash
docker compose up -d --build
# dann http://localhost:8080 öffnen
```

Details, Bedienung und Einstellungen: [Handbuch](docs/manual/de/index.html) ([English](docs/manual/en/index.html)); die App liefert es
unter `/manual/<Version>/` aus. Die App hat **keine Anmeldung**: nur im vertrauenswürdigen Netz betreiben, siehe [SECURITY.md](SECURITY.md).

### Funktionen

- **Import** von LabRadar-SD-Karten (Ordner `LBR`, ZIP; mehrere Karten gleichzeitig, auch per Drag & Drop) und von GRT-Dateien
  (`.grtload`, legt die Laborierung samt Serien an); Duplikaterkennung auch zwischen SD-Karte und GRT
- Laborierungen mit Stammdaten (Pulver, Menge, Hülse, Zünder, Geschoss, Setztiefe, …) und Waffenliste; Übersicht als Karten oder Liste,
  optional nach Waffe gruppiert; eine Serie kann in mehreren Laborierungen liegen
- Serien und Schüsse: Diagramm Geschwindigkeit über Distanz mit Werteanzeige, Auswahl per Klick, Ausreißer ausschließen, Statistik (Ø, SD, ES),
  Energie, **Impuls (MIP)**, **Ballistischer Koeffizient (G1/G7)**, Signalstärke, Geschossgewicht überschreiben
- Ladeleitern und Setztiefen-Tests als Darstellung der Messungen, Serienvergleich (bis 60 Serien) mit Trendlinie
- PDF-Berichte (Serie, Laborierung, Vergleich) und CSV-Export
- Seite *System*: Sprache (DE/EN), Einheiten (m/s·J ↔ fps·ft-lbf), Datensicherung herunterladen und wiederherstellen, Version

### Entwicklung

```bash
cd backend  && uv sync && uv run pytest && uv run ruff check src tests
cd frontend && npm ci && npm test && npm run typecheck && npm run build      # Node 24
uv run --project backend python scripts/smoke_test.py http://127.0.0.1:8080   # Smoketest gegen laufende Instanz
uv run --project backend python -m loadlog.synth ./synthetic-sd                # synthetische SD-Karte
```

Aufbau: `backend/` (FastAPI, SQLite, WeasyPrint), `frontend/` (Preact, TypeScript), `docs/` (Handbuch, Format-Wissen, Architektur), `scripts/`.
Version und Änderungen: [CHANGELOG.md](CHANGELOG.md). Architektur: [docs/architektur.md](docs/architektur.md). Dateiformate:
[docs/labradar-format.md](docs/labradar-format.md), [docs/grt-format.md](docs/grt-format.md). Beiträge: [CONTRIBUTING.md](CONTRIBUTING.md).

### Datenschutz

Echte Messdaten gehören nicht ins Repository. Beispiel- und Testdaten werden ausschließlich synthetisch erzeugt (`loadlog.synth`).
LoadLog sendet keine Daten an die Autoren oder an Dritte und lädt nichts aus dem Internet nach (Ausnahme: die optionale API-Dokumentation unter `/api/docs`, deren Swagger-Oberfläche Skripte von `cdn.jsdelivr.net` lädt). Wer die App für andere betreibt (z. B. in einem Verein),
ist selbst für den Datenschutz verantwortlich.

### Lizenz

[MIT](LICENSE). Hinweise zu Bibliotheken Dritter (u. a. LGPL-3.0): [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## English

Load **journal** and evaluation for chronograph data: imports the SD card data of a **LabRadar** (unofficial, not affiliated with the
manufacturer) as well as GRT files (`.grtload`), assigns series to loads, excludes outliers and shows statistics, impulse, ballistic
coefficient, velocity tracks, series comparisons, charge ladders and trends. PDF reports, CSV export. UI and manual in German and English.

### Scope: a journal, not load development

LoadLog **records and evaluates what you loaded and measured yourself**. It is **not a tool for developing loads**:

- It does **not calculate load data** and gives **no load recommendations**: no powder charges, no starting or maximum loads,
  no "best" load, no pressure or safety calculations.
- It does **not replace** the load tables, manuals or specifications of the manufacturers.
- All data on powder, charge, bullet, seating depth etc. is **purely your own input**. LoadLog checks it neither for plausibility nor for safety.
- Evaluations (average, standard deviation, energy, impulse, ballistic coefficient, etc.) are computed approximations from the measured values.
- All sample data in the manual, screenshots and demo (powder, charges, bullet weights, velocities) is **fictional**, not load data, and must **not be loaded or replicated**.

### Disclaimer

**Reloading is dangerous.** Wrong or improper loads can cause overpressure, destruction of the firearm, serious injury or death.
**You, the reloader, are solely responsible**: for your load data (only from reliable, current manufacturer sources), for your care, for the
safe handling of firearms and ammunition, and for complying with applicable laws and regulations.

LoadLog is provided **free of charge, "as is" and without warranty of any kind** (see the [MIT License](LICENSE)). Liability for intent and
gross negligence, for injury to life, body or health, and under mandatory statutory provisions (e.g. product liability law) **remains
unaffected**. Otherwise, to the extent permitted by law, the authors and contributors are **not liable** for damages of any kind, in
particular property damage and consequential damage, arising from the use or non-use of the software, from errors, incorrect
measurements, calculations or displays, or from data loss. **Never rely on LoadLog alone** for safety-relevant decisions or for
competition scoring. For users to whom German law applies, this liability regime applies instead of the warranty and liability disclaimer of the MIT License wherever the two differ. This text is not legal advice.

LabRadar and Gordon's Reloading Tool are trademarks or products of their respective owners. LoadLog is an independent, unofficial project
and is not affiliated with them.

### Quick start

```bash
docker compose up -d --build
# then open http://localhost:8080
```

Details, usage and settings: [manual](docs/manual/en/index.html) ([Deutsch](docs/manual/de/index.html)); the app serves it at
`/manual/<version>/`. The app has **no login**: run it only on a trusted network, see [SECURITY.md](SECURITY.md).

### Features

- **Import** of LabRadar SD cards (`LBR` folder, ZIP; several cards at once, also by drag and drop) and of GRT files
  (`.grtload`, creates the load with its series); duplicate detection, also between SD card and GRT
- Loads with master data (powder, charge, case, primer, bullet, seating depth, …) and a firearm list; overview as cards or list,
  optionally grouped by firearm; a series can belong to several loads
- Series and shots: velocity-over-distance chart with value display, selection by click, exclude outliers, statistics (avg, SD, ES),
  energy, **impulse (MIP)**, **ballistic coefficient (G1/G7)**, signal strength, bullet weight override
- Charge ladders and seating tests as a presentation of the measurements, series comparison (up to 60 series) with a trend line
- PDF reports (series, load, comparison) and CSV export
- *System* page: language (DE/EN), units (m/s·J ↔ fps·ft-lbf), download and restore a backup, version

### Development

```bash
cd backend  && uv sync && uv run pytest && uv run ruff check src tests
cd frontend && npm ci && npm test && npm run typecheck && npm run build      # Node 24
uv run --project backend python scripts/smoke_test.py http://127.0.0.1:8080   # smoke test against a running instance
uv run --project backend python -m loadlog.synth ./synthetic-sd                # synthetic SD card
```

Layout: `backend/` (FastAPI, SQLite, WeasyPrint), `frontend/` (Preact, TypeScript), `docs/` (manual, format notes, architecture), `scripts/`.
Version and changes: [CHANGELOG.md](CHANGELOG.md). Architecture: [docs/architektur.md](docs/architektur.md) (German). File formats:
[docs/labradar-format.md](docs/labradar-format.md), [docs/grt-format.md](docs/grt-format.md) (German). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

### Privacy

Real measurement data does not belong in the repository. Sample and test data is generated synthetically only (`loadlog.synth`).
LoadLog sends no data to the authors or to third parties and loads nothing from the internet (exception: the optional API documentation at `/api/docs`, whose Swagger interface loads scripts from `cdn.jsdelivr.net`). Anyone who runs the app for others
(e.g. in a club) is responsible for data protection themselves.

### License

[MIT](LICENSE). Notices for third-party libraries (incl. LGPL-3.0): [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
