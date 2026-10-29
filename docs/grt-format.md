# GRT-Datei (`.grtload`) als Importquelle

GRT (Gordon's Reloading Tool) speichert eine Laborierung samt den eingebetteten LabRadar-Messungen in einer
XML-Datei. Das ist oft die einzige verbliebene Kopie, wenn die SD-Karten-Originale nicht mehr vorliegen.
Stand der Analyse: Dateiversion "2021.x"; Quelle der Erkenntnisse war eine echte Datei (liegt nicht im Repo).

## Struktur

```
GordonsReloadingTool
└─ InnerBallistikInput
   ├─ title                      URL-kodiert, enthält Kaliber, Geschoss, Pulver
   ├─ gun / caliber / projectile / propellant   Listen von <input name value unit type descr/>
   └─ appendix
      ├─ note
      └─ Measurement
         └─ charge  (= eine Serie)   name, note, value, menu, source, ...
            └─ shot  (= ein Schuss)  name, velocity, V0, V<dist>, note, pressure
               └─ track  (time, velo, dist)  optional, ~40-130 Punkte
```

Alle Textattribute sind URL-kodiert (`%20`, `%C2%B0`, ...).

## Felder und Abbildung auf LoadLog

| GRT | Bedeutung | LoadLog |
|---|---|---|
| `charge@name` | "Series 47" oder frei benannt | Serien-Nr. aus der Endziffer, sonst 0 |
| `charge@value` | **Pulvermenge in kg** (Ladeleiter-Stufe) | `series.charge_gr` (÷ 6,479891e-5) |
| `charge@note` | freie Notiz | `series.note` |
| `charge@menu` | `V0;V5;V25;...` Distanzen in m (`menuunit`) | Distanzen der Schussdaten |
| `shot@V0`, `shot@V<d>` | Geschwindigkeit in m/s, **auf 1 m/s gerundet**; `0` = nicht gemessen | `v0_ms`, `velocities_ms` |
| `shot@note` | Zeitstempel `MM-DD-YYYY HH:MM:SS` | `taken_at` |
| `shot/track@time` | **Millisekunden** | `time_s` (÷ 1000) |
| `shot/track@velo`, `@dist` | m/s, m | Trackpunkte; Track-V0 ist genauer als `@V0` und wird bevorzugt |
| `projectile@mp` | Geschossgewicht in g | `weight_g` je Schuss, `bullet_weight_gr` der Laborierung |
| `projectile@mname/pname/lotid` | Hersteller/Typ/Los | `bullet_maker/_type/_lot` |
| `propellant@mname/pname/lotid` | Hersteller/Typ/Los | `powder_maker/_name/_lot` |
| `caliber@oal`, `projectile@gdepth` | Patronenlänge, Setztiefe | `coal_mm`, `seating_depth_mm` |

Nicht in der Datei: Signalstärke (Balken), SNR der Trackpunkte, Geräte-ID, Ke/PF. Energie wird aus
Gewicht und Geschwindigkeit berechnet (½·m·v²), die Signalstärke bleibt leer.

Serien ohne Track und ohne Distanzwerte kommen vor (manuell erfasste oder aus der LabRadar-App übernommene
Messungen mit nur V0). Dieselbe Serien-Nr. kann mehrfach vorkommen (verschiedene SD-Karten); Eindeutigkeit
liefert der Zeitstempel des ersten Schusses (`source_key`).

## Import-Verhalten

- `POST /api/import` erkennt `<GordonsReloadingTool` am Dateianfang; sonst wird ZIP erwartet.
- Ohne `load_id`: aus den Kopfdaten wird eine Laborierung angelegt (Typ `ladder`, wenn mehrere Pulvermengen
  vorkommen) und alle **neuen** Serien werden ihr zugeordnet.
- Mit `load_id` (Import aus der Laborierung heraus): nur Zuordnung der neuen Serien; leere Kopffelder der
  Laborierung werden ergänzt, vorhandene nie überschrieben. Beim ZIP-Import (SD-Karte) wird ebenfalls
  nur zugeordnet.
- Bereits vorhandene Serien werden übersprungen. GRT liefert keine Geräte-ID und damit einen anderen `source_key`; dieselbe Serie aus
  SD-Karte und GRT erkennt LoadLog deshalb über den ersten Schuss (±2 s), die Schusszahl und V0 (±1,5 m/s): SD nach GRT wertet die
  GRT-Serie mit den genaueren Daten auf, GRT nach SD wird übersprungen.
- XML-Härtung: DOCTYPE/ENTITY werden abgelehnt, Größe max. 50 MB.

## Datenschutz

Echte `.grtload`-Dateien enthalten Notizen, Namen, Orte und Zeitstempel und gehören nie ins Repo. Tests nutzen
einen synthetischen Generator (`loadlog.synth.make_grtload`).

## Herkunft

Das Format wurde durch Analyse von Beispieldateien abgeleitet (Vergleich der XML-Daten mit den bekannten Messwerten), ohne Dekompilierung von
Hersteller-Software. Diese Datei enthält weder Herstellercode noch Herstellermaterial noch echte Messdaten. Es handelt sich um eine unabhängige,
unverbindliche Beschreibung für Interoperabilität; Marken gehören ihren Inhabern.
