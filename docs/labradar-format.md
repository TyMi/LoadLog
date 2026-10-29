# LabRadar: Dateiformate und Gerätewissen

Stand: 2026-10-27. Quellen: LabRadar-Handbuch v1.5
(<https://mylabradar.com/wp-content/uploads/2023/09/UserManual-V1.5-Labradar-EN.pdf>)
und die Analyse einer echten SD-Karten-Struktur (13 Serien, Daten nicht im
Repo). Werte unten sind synthetisch/generisch.

Kennzeichnung: **[Handbuch]** dokumentiert, **[verifiziert]** an Beispieldaten
gegen die CSVs geprüft, **[Annahme]** aus Daten abgeleitet, **[offen]** unbekannt.

## Ordnerstruktur der SD-Karte

```
LBR/
  LBR<Seriennr><Datum>.LID    leer, Dateiname enthält Geräte-Seriennummer  [verifiziert]
  SRnnnn/
    SRnnnn.lbr                Binärdatei, Serie komplett
    SRnnnn Report.csv         Serienübersicht
    TRK/ShotNNNN Track.csv    Radar-Track je Schuss
```

- Bis zu 9999 Serien mit je max. 100 Schüssen [Handbuch].
- Schüsse können nicht nachträglich zu einer alten Serie hinzugefügt werden;
  gelöschte Schussnummern werden nicht neu belegt, es gibt also Lücken
  [Handbuch]. Das Löschen einer Track-Datei ändert die Serie nicht, die
  `.lbr` ist maßgeblich (Forenbeobachtung, nicht dokumentiert).
- Nur Daten, die bei eingelegter SD-Karte aufgezeichnet wurden, sind per USB
  zugänglich [Handbuch].

## Messdistanzen (Dx1…Dx5)

Am Gerät einstellbar: fünf Distanzen in Schritten von 1, aufsteigend
(Handbuch-Beispiel 10/20/30/40/50). Pro Schuss ergeben sich V0 plus fünf
Werte [Handbuch].

- Der Power Factor (PF) wird mit der Geschwindigkeit bei `Dx1` berechnet
  [Handbuch]. Die Spalte heißt daher `PF<Dx1>`, z.B. `PF5`.
- Die Distanzen **ändern sich zwischen Serien** (Beispiel: 5/10/15/20/25 in
  älteren, 5/10/15/20/23 in neueren Serien) [verifiziert]. Der Parser darf
  Spaltennamen nie festverdrahten, sondern liest `V<n>`/`Ke<n>`-Spalten
  dynamisch.
- Einheit steht im Report-Kopf (`Units distances`).

## Trigger-Modus (steht nicht in den Dateien)

- **Doppler-Trigger:** V0 ist die Geschwindigkeit beim Eintritt in den
  Radarstrahl, nicht an der Mündung; alle Distanzen verschieben sich um
  diesen Abstand [Handbuch].
- **Interner/externer Trigger:** V0 ist die echte Mündungsgeschwindigkeit
  [Handbuch].
- Folge: Die App führt den Trigger-Modus als eigenes Metadatum pro Serie.

## `SRnnnn Report.csv`

- Trennzeichen `;`, erste Zeile `sep=;`, Zeilenende CRLF.
- **Eigenheit:** In neueren Dateien sind Zeilen mit NUL-Bytes aufgefüllt
  (UTF-16-Artefakt, Zeilen beginnen mit `\0` und enden mit NUL/Leerzeichen
  vor CRLF) [verifiziert]. Parser: NULs entfernen, Whitespace trimmen.
- Kopf (Schlüssel;Wert;Einheit): Geräte-ID, Serien-Nr., Schusszahl, Einheiten
  (Geschwindigkeit, Distanz, Energie, Gewicht), Statistik (Average, Highest,
  Lowest, Ext. Spread, Std. Dev), jeweils mit zwei Nachkommastellen.
- Tabelle: `Shot ID; V0; V<d1>…V<d5>; Ke0; Ke<d1>…Ke<d5>; PF<d1>;
  Proj. Weight; Date; Time;` (abschließendes `;`).
- V und Ke sind auf ganze Zahlen **gerundet** [verifiziert].
- Datum `MM-TT-JJJJ`, Zeit `HH:MM:SS` [verifiziert]. Projektilgewicht in der
  Geräteeinheit (grain).
- Die Kopfstatistik umfasst **alle** Schüsse, nicht nur gewertete.

## `ShotNNNN Track.csv`

```
sep=;
Device ID;<ID>;;
Series No;<nnnn>
Shot No;<nnnn>
<leer>
Time (s);Vel (m/s);Dist (m);SNR
0.000000;<v>;0.00;-
0.021021;<v>;5.74;33.72
...
```

- Rund 30–50 Messpunkte pro Schuss, Raster ca. 2 ms [verifiziert].
- Erste Zeile hat SNR `-`; der Track endet je nach Schuss bei ca. 25–35 m
  [verifiziert].
- SNR ist die Messgröße für die Erfassungsqualität pro Punkt (Wertebereich
  grob 7–35 in den Beispielen) [Handbuch erwähnt SNR].

## `SRnnnn.lbr` (Binärformat)

Little-endian. 28 Byte Kopf + 100 Byte je Schuss; die Länge geht bei allen
Beispieldateien ohne Rest auf [verifiziert].

### Kopf (28 Byte)

| Offset | Typ | Inhalt |
|---|---|---|
| 0 | u8 | konstant 1 (Version?) [Annahme] |
| 1 | u8 | Schusszahl [verifiziert] |
| 2 | u8 | Serien-Nr. [verifiziert] |
| 3 | u8 | 0 |
| 4–7 | 4 B | unbekannt [offen] |
| 8–27 | 5×f32 | Mittelwert, Höchst, Tiefst, ES, SD (m/s) [verifiziert] |

### Schuss-Satz (100 Byte)

| Offset | Typ | Inhalt |
|---|---|---|
| 0 | u8 | Serien-Nr. |
| 1 | u8 | 0 |
| 2 | u8 | Schuss-Nr. |
| 3–7 | 5×u8 | Sekunde, Minute, Stunde, Tag, Monat |
| 8–9 | u16 | Jahr |
| 10–11 | 2 B | 0 |
| 12 | f32 | Projektilgewicht in **Gramm** (z.B. 14.904 g = 230 gr) |
| 16 | f32 | konstant 0,15 in allen Beispielen [offen] |
| 20 | u32 | Flag: 0 in alten, 1 in neueren Serien [offen] |
| 24 | f32 | V0 |
| 28 | f32 | Ke0 |
| 32 | f32 | PF (bei Dx1) |
| 36–55 | 5×f32 | V bei Dx1…Dx5 [verifiziert] |
| 56–75 | 5×f32 | Distanzen Dx1…Dx5 |
| 76–95 | 5×f32 | Ke bei Dx1…Dx5 |
| 96 | u32 | Signalstärke 1–5 |

- Die **Signalstärke** (Offset 96) korreliert mit dem mittleren SNR des Tracks
  (Serien mit SNR ≈ 14–16 haben 1–2, mit ≈ 28–33 haben 4–5) und entspricht
  vermutlich der 5-Balken-Anzeige am Gerät (5 = beste, 1 = schlechtes Signal
  [Handbuch]) [Annahme].
- V/Ke sind hier mit Nachkommastellen gespeichert, genauer als die CSV.

## Weitere Gerätehinweise [Handbuch]

- Fehlermeldung "Acquisition error: could not track the projectile": der
  Schuss wird **nicht** aufgezeichnet.
- Arm-Zeit 10–300 s einstellbar; Projektil-Offset (6/12/18") beeinflusst die
  Messgenauigkeit.
- Projektilgewicht wird am Gerät pro Schuss gesetzt und in die Datei
  geschrieben.

## Offene Punkte

- Kopf-Bytes 4–7, Wert 0,15, Flag (Offset 20): mit weiteren Serien aus
  unterschiedlicher Gerätekonfiguration vergleichen (Trigger-Modus,
  Einheiten, Firmware).
- Einheiten-Varianten (fps, yd, ft) im Report: Beispieldaten fehlen, bisher
  nur m/s, m, ft-lbf, grain gesehen.
- LabRadar LX hat laut Handbuch (LX-Version) nur eine Distanz-Einstellung;
  Format nicht geprüft.

## Herkunft

Das Format wurde aus Beispieldateien (Vergleich der Binärdatei mit den zugehörigen CSV-Dateien) und dem öffentlich verfügbaren Handbuch des
Geräts abgeleitet, ohne Dekompilierung von Hersteller-Software. Diese Datei enthält weder Herstellercode noch Herstellermaterial noch echte
Messdaten. Es handelt sich um eine unabhängige, unverbindliche Beschreibung für Interoperabilität; Marken gehören ihren Inhabern.
