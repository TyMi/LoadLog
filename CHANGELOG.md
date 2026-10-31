# Änderungen

Versionsnummern sind dreistufig (`Major.Minor.Patch`) und werden von Hand erhöht. Das Handbuch gilt für `Major.Minor`.

## 0.0.11

- **Papierkorb:** Gelöschte Serien und Laborierungen werden nicht mehr sofort entfernt, sondern in den Papierkorb (Menü *Papierkorb*) verschoben. Von dort lassen sie sich wiederherstellen (Serien samt ihren Zuordnungen) oder endgültig löschen, einzeln oder mit *Papierkorb leeren*. Es wird nichts automatisch gelöscht. Eine Sicherung enthält den Papierkorb; Waffen werden weiterhin sofort gelöscht.
- **Verhalten:** Serien einer gelöschten Laborierung bleiben erhalten und gelten bis zur Wiederherstellung als nicht zugeordnet. Importierst du eine Serie erneut, deren Kopie im Papierkorb liegt, ersetzt der neue Import die Kopie.
- **Schnittstelle:** `GET /api/trash`, `POST /api/trash/{series|loads}/{id}/restore`, `DELETE /api/trash/{series|loads}/{id}` und `DELETE /api/trash`. `DELETE /api/series/{id}` und `DELETE /api/loads/{id}` verschieben jetzt in den Papierkorb.
- **Datenbank:** Schema 6 (Spalte `deleted_at` bei `series` und `loads`); ältere Datenbanken und Sicherungen werden migriert.

## 0.0.10

- **Status der Laborierung:** Entwurf, in Prüfung, bewährt oder ausgemustert (oder ohne Angabe), als Marke in Karten und Liste sichtbar.
- **Duplizieren:** Eine Laborierung lässt sich als Entwurf mit denselben Stammdaten (ohne Serien) kopieren; die Kopie verweist auf ihre Vorlage, die Vorlage listet ihre Varianten. Schnittstelle `POST /api/loads/{id}/duplicate`.
- **Suchen und Filtern:** Die Übersicht sucht nach Name, Pulver, Geschoss, Waffe, Hülse, Zünder und Notiz und filtert nach Status.
- **Gruppengröße:** Freies Textfeld an der Serie (z. B. „25 mm auf 100 m“), auch im PDF-Bericht der Serie.
- **Datenbank:** Schema 5 (neue Spalten `loads.status`, `loads.parent_id`, `series.group_text`); ältere Datenbanken und Sicherungen werden beim Öffnen bzw. Wiederherstellen migriert.

## 0.0.9

- **Englisch durchgängig im britischen Format:** PDF-Berichte und CSV-Export zeigen auf Englisch das Datum als `dd/mm/yyyy` (Kopfzeile des Berichts mit Uhrzeit `dd/mm/yyyy hh:mm`); die Oberfläche tat das schon. Deutsch unverändert `tt.mm.jjjj`. Das ISO-Datum der Version 0.0.8 entfällt.
- **Import in eine Laborierung:** Neues Häkchen *Vorhandene Serien auch dieser Laborierung zuordnen* (standardmäßig aus). Serien, die LoadLog schon hat, werden dann zusätzlich in die Laborierung gelegt (auch aus einer GRT-Datei oder von der SD-Karte erkannt), statt übersprungen zu werden; die Meldung nennt sie. Schnittstelle: `POST /api/import?load_id=&assign_existing=true`, Antwort mit `assigned`.
- **CI:** Neuer Workflow `audit.yml` (wöchentlich, von Hand und bei Änderung der Sperrdateien) prüft die Abhängigkeiten mit `pip-audit` und `npm audit`. Er ist nur meldend und kein Pflicht-Check.

## 0.0.8

- **Englische PDF-Berichte:** Das Datum der Serien steht wie „Created“ und der CSV-Export als `yyyy-mm-dd` (bisher `dd/mm/yyyy`); die Oberfläche zeigt auf Englisch weiterhin `dd/mm/yyyy`.
- **Dokumentation:** `docs/architektur.md` führt jetzt alle Schnittstellen auf (mit Parametern); `CONTRIBUTING.md` legt die Sprache der Dokumentation fest.

## 0.0.7

Härtung aus der unabhängigen Prüfung.

- **Fremde Webseiten:** Schreibende Anfragen mit fremdem oder `null`-`Origin` werden abgewiesen (zusätzlich zu `Sec-Fetch-Site`); `Origin` darf zum Host der Anfrage, zu `X-Forwarded-Host` oder zu `LOADLOG_ALLOWED_HOSTS` passen. API-Antworten tragen `Cache-Control: no-store`.
- **Betrieb im Netz:** Ist die App an eine Netzadresse gebunden und `LOADLOG_ALLOWED_HOSTS` leer, schreibt der Start eine Warnung ins Protokoll. Das Handbuch hat eine Checkliste für den Betrieb im Intranet (Host-Namen, Reverse-Proxy, TLS, Sicherungen), SECURITY.md ist präzisiert (Bindung im Container).
- **Wiederherstellen:** Die Prüfung der Sicherung umfasst jetzt Fremdschlüssel und die JSON-Spalten der Schüsse; eine präparierte Datei wird abgelehnt, bevor die laufenden Daten ersetzt werden. `LOADLOG_ALLOW_RESTORE=0` schaltet das Wiederherstellen ab.
- **Sicherheitskopien:** Es bleiben die neuesten N Kopien unter `backups/` (Standard 5, einstellbar unter *Einstellungen*, Datei `settings.json` im Datenordner).
- **Grenzen:** GRT-Dateien sind auf 10 MB begrenzt (echte Dateien: etwa 1,5 MB). `docker-compose.yml`: Speicher- und Prozessgrenze (`LOADLOG_MEM_LIMIT`, Standard 1 GB), `/tmp` mit `noexec,nosuid`.

## 0.0.6

- **GRT-Import:** Pulvermenge (`mc`) und Pulvertemperatur (`pt`) der Kopfdaten werden mit ihrer Einheit übernommen (Gramm, Kilogramm, Celsius, Kelvin, Fahrenheit; bei unbekannter Einheit oder unplausiblem Wert bleibt das Feld leer). Die Leiterdefinition (Stufenzahl, Schrittweite) steht in der Notiz der Laborierung und setzt bei Dateien ohne Messdaten den Typ *Ladeleiter*.
- **GRT ohne Messdaten:** Enthält die Datei keine Messreihen, wird nur die Laborierung angelegt, mit Hinweis; bisher wurde die Datei abgelehnt und die Kopfdaten gingen verloren.
- **Serienbezeichnung:** Haben mehrere Messgruppen einer GRT-Datei denselben Namen (z. B. zweimal „Series 15“), erhalten die weiteren einen Zähler („Series 15 (2)“).
- **Dokumentation:** Handbuch (Import) und `docs/grt-format.md` beschreiben die zusätzlichen Felder, Dateien ohne Messdaten und die Namensregel.

## 0.0.5

Fehlerkorrekturen aus einer unabhängigen Prüfung.

- **Schuss ausschließen:** Die Serienseite friert dabei nicht mehr ein; die Antwort des Servers enthält jetzt wie beim Laden der Seite auch die Laborierungen.
- **Import:** Doppelte Schussnummern in einer Serie führen nicht mehr zu einem Serverfehler; der erste Schuss zählt, der Rest wird übersprungen und gemeldet.
- **Eingaben:** `NaN` und `Infinity` werden mit einer Meldung abgelehnt (statt Serverfehler). Fehler bei Zahlen und Texten erscheinen übersetzt (Deutsch/Englisch) statt als englische Rohmeldung. Namen aus Leerzeichen werden abgelehnt, Leerraum am Rand wird entfernt; ein leerer Serienname bedeutet „ohne Namen“.
- **Zahlenfelder:** Es gelten nur Ziffern mit Komma oder Punkt (`0x10`, `1e3` und `1.234,5` werden abgelehnt).
- **Löschen:** Fehler beim Löschen von Laborierung oder Waffe werden angezeigt; die Rückfrage nennt, in wie vielen Laborierungen die Waffe verwendet wird. Hinweise zum angewendeten Gewicht bei Serien in mehreren Laborierungen.
- **Oberfläche:** Importseite und Laborierungsformular folgen einem Sprachwechsel (Meldungen, Dezimalzeichen).

## 0.0.4

- **Handbuch:** Im Abschnitt Ladeleitern und Setztiefen steht ausdrücklich, dass alle Werte in den Beispielen und Screenshots erfunden und keine Ladedaten sind (Deutsch und Englisch).

## 0.0.3

- **CI:** Zusätzlicher Job `docker-arm64`: Docker-Build und Smoketest auf einem ARM64-Runner (Raspberry Pi, Docker auf Apple Silicon, ARM-NAS). Der Job ist kein Pflicht-Check für Pull Requests.

## 0.0.2

Änderungen nach der Veröffentlichung auf GitHub.

- **CI:** Die Workflows lassen sich zusätzlich von Hand starten (`workflow_dispatch`).
- **Deutsches Datumsformat:** Im CSV-Export steht das Datum auf Deutsch als `tt.mm.jjjj` (Uhrzeit `hh:mm:ss`); Oberfläche und PDF-Berichte nutzten es bereits.
- **Haftungsausschluss:** Gefahrenhinweise zu Überdruck, Verletzung und Tod entfernt; Verantwortung, Gewährleistungs- und Haftungsregelung unverändert. In der App „auf eigene Verantwortung“ statt „auf eigene Gefahr“.
- **README:** Zwei Screenshots (Serienansicht, Serienvergleich; fiktive Beispieldaten) in der deutschen und englischen Fassung.
- **Einstellungen:** Der Menüpunkt *System* heißt jetzt *Einstellungen* (Adresse `#/settings`).
- **Technik:** Node 26 (LTS) für den Frontend-Build, Dependabot nur für LTS-Versionen von Node, Python-Abhängigkeiten aktualisiert.
- **Handy-Ansicht:** Tabellen (Serien einer Laborierung, Schüsse, Serienvergleich) erscheinen auf schmalen Bildschirmen als Karten mit Beschriftung über jedem Wert; nichts wird mehr abgeschnitten, Knöpfe und Beschriftungen brechen nicht mehr unglücklich um.

## 0.0.1

Erster Stand.

- **Import:** LabRadar-SD-Karten (Ordner, ZIP, mehrere gleichzeitig, Drag & Drop, auch Ordnerwahl am Mac) und GRT-Dateien
  (`.grtload`, legt Laborierung und Serien an). Import auch direkt in einer Laborierung. Mehrfachauswahl mit Zuordnen,
  Rückgängig und Löschen. Duplikaterkennung, auch zwischen SD-Karte und GRT (SD nach GRT wertet auf, GRT nach SD wird übersprungen).
  Ein Import läuft in einer Transaktion; unplausible Werte werden verworfen und gemeldet.
- **Laborierungen:** Übersicht als Karten oder Liste, optional nach Waffe gruppiert. Eine Serie kann in mehreren Laborierungen liegen.
  Serien benennen und nach Datum, Pulvermenge oder Name sortieren. Gewicht der Laborierung auf alle Serien anwenden.
- **Serien:** Diagramm Geschwindigkeit über Distanz mit Werteanzeige und Auswahl per Klick auf Linie oder Zeile, ausgeschlossene Schüsse
  grau und gestrichelt, Datum einmal im Kopf. Kennzahlen in drei Gruppen: Geschwindigkeit, Energie und Impuls (MIP, ganzzahlig
  gerundet, mit Minimum), Ballistik (BC G1 und G7 aus der Geschwindigkeitsabnahme). Geschossgewicht je Serie überschreibbar, Warnung bei
  Abweichung von der Laborierung.
- **Vergleich:** bis 60 Serien, Beschriftungen werden ausgedünnt, Zurück führt zur gemeinsamen Laborierung.
- **Export:** PDF-Berichte (mit Impuls und BC) und CSV je Serie und Laborierung (Excel-tauglich, Formelzeichen entschärft).
- **Einstellungen:** Sprache und Einheiten, Datensicherung herunterladen und wiederherstellen (mit automatischer Sicherung des alten Stands,
  Prüfung der Datei, Schutz gegen fremde Webseiten), Version, Handbuch.
- **Meldungen:** Der Server liefert Code und Parameter, die Oberfläche übersetzt auf Deutsch und Englisch.
- **Abgrenzung und Haftungsausschluss:** README (Deutsch und Englisch), Handbuch und Seite *Einstellungen* stellen klar, dass LoadLog ein Journal ist und keine Laborierungsentwicklung (keine Ladedaten, keine Empfehlungen), und dass der Wiederlader selbst verantwortlich ist.
- **Rechtliche Hinweise:** Haftungsklausel mit ausdrücklichem Vorbehalt für Vorsatz, grobe Fahrlässigkeit, Leben, Körper, Gesundheit und Produkthaftung; Haftungshinweis am Ende jedes PDF-Berichts; `THIRD_PARTY_NOTICES.md` (u. a. LGPL-3.0 für `py_ballisticcalc`) auch im Docker-Image; Herkunftsvermerk der Formatbeschreibungen; Beitragsbedingung (inbound = outbound); Impulsformel mit Quelle (Sportordnung des DSB, Regel 2.21.1) und Hinweis, dass LoadLog die offizielle Munitionsprüfung nicht ersetzt; Hinweis, dass alle Beispieldaten fiktiv sind; GitHub Actions per Commit-SHA festgelegt.
- **Handbuch:** Deutsch und Englisch mit eigenen Screenshots (nur synthetische Daten), liegt unter `/manual/0.0/<Sprache>/`.
- **Technik:** Schema 4 (Serie und Laborierung n:m, automatische Migration), Python 3.15 im Container (CI testet 3.12 und 3.15),
  Node 26, weitgehend reproduzierbarer Docker-Build (Image-Digests, Lock-Dateien mit Hashes; Debian-Pakete nicht versionsfest), CI mit gitleaks-Secret-Scan, Dependabot.
- **Nach unabhängiger Prüfung (Opus-Agent):** Wiederherstellung migriert und prüft eine Arbeitskopie, bevor die laufenden Daten ersetzt werden (und überschreibt keine Sicherheitskopie mehr); schreibende Anfragen von fremden Webseiten werden abgewiesen, optional Host-Liste (`LOADLOG_ALLOWED_HOSTS`); Uploadgrenze vorab per Anfragegröße, Wiederherstellungsgrenze 200 MB; `/redoc` entfernt; defekte ZIP-Einträge und Seriennummern über 255 werden abgefangen; Gewichtsgrenze auch für "Gewicht der Laborierung anwenden"; lesbare Fehlermeldungen beim Import; Regelauslegung zum Mindestimpuls korrigiert; vollständige Lizenzliste und Lizenztexte im Image; Test für den Haftungsausschluss.
- **Eingabehärtung (Fuzz-Tests, Berichte, Upload):** Uploads ohne Längenangabe werden abgelehnt (411); PDF-Berichte laden keine externen
  Ressourcen (nur `data:`); zufällig veränderte LBR-, CSV-, GRT- und ZIP-Dateien führen nur zu Meldungen: beschädigte ZIP-Kopfdaten
  (zuvor Fehler 500), unbekannte XML-Kodierung und UTF-16-GRT-Dateien werden abgewiesen.
  Oberflächentests: Nutzertext mit HTML (Namen, Notizen) erscheint nur als Text; `dangerouslySetInnerHTML` ist auf das Server-SVG beschränkt.
- **Laborierungen und Beispieldaten:** Hinweis bei Ladeleitern, dass die Gesamtkennzahlen (Ø, SD, ES) Stufen mit unterschiedlicher
  Pulvermenge mischen; synthetische Tracks liefern plausible BC-Werte (G7 etwa 0,16 bis 0,25). Haftungsklausel: für Nutzer unter deutschem
  Recht gilt sie anstelle des Gewährleistungs- und Haftungsausschlusses der englischen MIT-Lizenz, soweit beide abweichen.
- **Härtung** nach unabhängiger Prüfung: nicht endliche und unplausible Werte, null-Felder in PUT, riesige IDs, defekte Tracks,
  übergroße Dateien in der ZIP, Standard-Bindung an 127.0.0.1.
