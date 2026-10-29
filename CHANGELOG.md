# Änderungen

Versionsnummern sind dreistufig (`Major.Minor.Patch`) und werden von Hand erhöht. Das Handbuch gilt für `Major.Minor`.

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
