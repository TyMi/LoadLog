# Sicherheitsrichtlinie

## Sicherheitslücken melden

Bitte **keine** öffentlichen Issues für Sicherheitsprobleme anlegen.
Nutze stattdessen die private Meldefunktion von GitHub
(*Security* → *Report a vulnerability*) im Repository.

Du erhältst nach Möglichkeit innerhalb einer Woche eine Rückmeldung.

## Unterstützte Versionen

Solange es kein stabiles Release gibt, wird nur der aktuelle Stand des
`main`-Branches betreut.

## Betriebshinweise

- LoadLog hat **keine Authentifizierung** und soll nur in einem vertrauenswürdigen Netz laufen (Heimnetz, Intranet ohne Zugang von außen).
  Der Server bindet ohne Angabe an `127.0.0.1`. Im Container lauscht das Programm auf `0.0.0.0`; lokal bleibt es nur durch die Port-Veröffentlichung
  der mitgelieferten `docker-compose.yml` (`LOADLOG_BIND`, Standard `127.0.0.1`). Ein eigenes `docker run -p 8080:8080` ist für das ganze Netz offen.
  Für den Zugriff aus dem Netz `LOADLOG_BIND` bewusst setzen und `LOADLOG_ALLOWED_HOSTS` (kommagetrennte Host-Namen, Schutz vor DNS-Rebinding)
  ausfüllen; ohne diese Angabe warnt der Start im Protokoll. Bei mehreren Nutzern oder nicht vertrauenswürdigen Geräten einen Reverse-Proxy mit
  Anmeldung und TLS davorsetzen (Host-Kopf unverändert durchreichen oder `X-Forwarded-Host` setzen). Details: Handbuch, Abschnitt
  „Sicherheit und Netzwerk“.
- Uploads sind auf 50 MB begrenzt (GRT-Dateien auf 10 MB, Sicherungen auf 200 MB, vorab anhand der Anfragegröße geprüft, Uploads ohne Längenangabe
  mit 411 abgelehnt), ZIPs werden nur im Speicher gelesen (kein Entpacken auf die Platte, Pfade mit `..` werden ignoriert, Größen- und Anzahlgrenzen).
- Schreibende Anfragen, die der Browser von einer fremden Webseite aus schickt (`Sec-Fetch-Site: cross-site` oder `same-site`, abweichender `Origin`),
  werden abgewiesen. Das ersetzt keine Anmeldung. API-Antworten sind nicht zwischenspeicherbar (`Cache-Control: no-store`).
- Das Wiederherstellen prüft die Datei vollständig (Aufbau, Fremdschlüssel, JSON-Spalten) und legt vorher eine Sicherheitskopie unter `backups/`
  ab (Anzahl einstellbar, Standard 5). Mit `LOADLOG_ALLOW_RESTORE=0` lässt es sich abschalten.
- Bei Start über die mitgelieferte `docker-compose.yml` läuft der Container als unprivilegierter Benutzer, mit schreibgeschütztem
  Dateisystem (`/tmp` ohne `exec`), ohne zusätzliche Linux-Capabilities, mit Grenzen für Speicher und Prozesse und standardmäßig nur auf
  `127.0.0.1`. Bei einem eigenen `docker run` diese Einstellungen selbst setzen.

## Datenschutz

LoadLog sendet keine Daten an die Autoren oder an Dritte und lädt nichts aus dem Internet nach (Ausnahme: die optionale API-Dokumentation unter `/api/docs`, deren Swagger-Oberfläche Skripte von `cdn.jsdelivr.net` lädt). Wer die App für andere betreibt
(z. B. in einem Verein), ist selbst für den Datenschutz verantwortlich.

## Hinweis zu Daten

Das Projekt verarbeitet lokale Messdateien. Bitte lade in Issues oder Pull
Requests keine echten Exporte mit Personenbezug hoch, sondern nur
anonymisierte oder synthetische Daten.
