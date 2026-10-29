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

- LoadLog hat **keine Authentifizierung**. Standardmäßig bindet der Container an
  `127.0.0.1`. Für den Zugriff aus dem Heimnetz bewusst `LOADLOG_BIND` setzen;
  für Zugriff aus dem Internet einen Reverse-Proxy mit Anmeldung und TLS davorsetzen.
- Uploads sind auf 50 MB begrenzt (Sicherungen auf 200 MB, vorab anhand der Anfragegröße geprüft, Uploads ohne Längenangabe mit 411 abgelehnt), ZIPs werden nur im Speicher gelesen
  (kein Entpacken auf die Platte, Pfade mit `..` werden ignoriert, Größen- und Anzahlgrenzen).
- Schreibende Anfragen, die der Browser von einer fremden Webseite aus schickt (`Sec-Fetch-Site: cross-site` oder `same-site`), werden
  abgewiesen. Mit `LOADLOG_ALLOWED_HOSTS` (kommagetrennt) lässt sich die App auf bestimmte Host-Namen beschränken (Schutz vor DNS-Rebinding).
  Beides ersetzt keine Anmeldung.
- Bei Start über die mitgelieferte `docker-compose.yml` läuft der Container als unprivilegierter Benutzer, mit schreibgeschütztem
  Dateisystem, ohne zusätzliche Linux-Capabilities und standardmäßig nur auf `127.0.0.1`. Bei einem eigenen `docker run` diese
  Einstellungen selbst setzen.

## Datenschutz

LoadLog sendet keine Daten an die Autoren oder an Dritte und lädt nichts aus dem Internet nach (Ausnahme: die optionale API-Dokumentation unter `/api/docs`, deren Swagger-Oberfläche Skripte von `cdn.jsdelivr.net` lädt). Wer die App für andere betreibt
(z. B. in einem Verein), ist selbst für den Datenschutz verantwortlich.

## Hinweis zu Daten

Das Projekt verarbeitet lokale Messdateien. Bitte lade in Issues oder Pull
Requests keine echten Exporte mit Personenbezug hoch, sondern nur
anonymisierte oder synthetische Daten.
