"""Meldungen mit stabilem Code und Parametern.

Der Server liefert Code, Parameter und einen deutschen Text als Rückfall; die Oberfläche übersetzt anhand des Codes
(DE/EN). Parameter dürfen selbst Meldungen sein (z. B. der Grund eines Fehlers).
"""

_DE = {
    # Import: ZIP und LabRadar
    "zip_invalid": "Keine gültige ZIP-Datei",
    "zip_too_many": "Zu viele Dateien im ZIP",
    "zip_too_big": "ZIP entpackt zu groß",
    "file_too_large": "Datei zu groß, übersprungen: {name}",
    "no_series": "Keine LabRadar-Serien gefunden (erwartet: LBR/SRnnnn/SRnnnn.lbr)",
    "series_label": "Serie {no}",
    "series_no_lbr": "{label}: ohne .lbr, nur gerundete Report-Werte",
    "series_skipped": "{label} übersprungen: {reason}",
    "track_ignored": "{label} Schuss {shot}: Track ignoriert ({reason})",
    "insane": "{label}: {n} Schuss/Schüsse mit unplausiblen Werten verworfen",
    "shot_duplicate": "{label}: {n} doppelte Schussnummer(n) übersprungen",
    "lbr_size": "Unerwartete Dateigröße: {bytes} Byte",
    "lbr_count": "Schusszahl im Kopf passt nicht zur Dateigröße",
    "lbr_time": "Ungültiger Zeitstempel in Schuss {shot}",
    "csv_datetime": "Unbekanntes Datums-/Zeitformat: {date} {time}",
    "csv_no_series": "Report ohne Serien-Nr.",
    "csv_bad_row": "Ungültige Zeile in Report: {row}",
    "csv_bad_track": "Ungültige Track-Zeile: {line}",
    # Import: GRT
    "grt_too_large": "Datei zu groß (GRT-Dateien höchstens 10 MB)",
    "grt_doctype": "DOCTYPE/ENTITY nicht erlaubt",
    "grt_bad_xml": "Kein gültiges XML: {reason}",
    "grt_not_grt": "Keine GRT-Datei (GordonsReloadingTool/InnerBallistikInput fehlt)",
    "grt_no_series": "Keine Messserien in der GRT-Datei gefunden",
    "grt_shot_skipped": "{label}: Schuss {shot} übersprungen (Zeit oder V0 fehlt)",
    "grt_track_invalid": "{label}: Schuss {shot}: Track mit ungültigen Werten ignoriert",
    "grt_series_empty": "{label}: ohne verwertbare Schüsse übersprungen",
    "grt_load_only": "Die Datei enthält keine Messdaten: nur die Laborierung wurde angelegt",
    "grt_weight_missing": "Geschossgewicht fehlt in der Datei: MIP und Energie sind nicht berechenbar",
    # Duplikate
    "duplicate_series": "{label} ist bereits als Serie {id} vorhanden und wurde übersprungen",
    "upgraded_series": "{label}: bestehende Serie {id} mit den genaueren Messdaten der SD-Karte aktualisiert",
    # API
    "not_found": "Nicht gefunden: {what}",
    "no_weight": "Die Laborierung hat kein Geschossgewicht",
    "upload_too_large": "Datei zu groß (max. {max} MB)",
    "pdf_unavailable": "PDF-Erzeugung nicht verfügbar (WeasyPrint/Pango fehlt)",
    "bad_theme": "Unbekanntes Theme",
    "bad_lang": "Unbekannte Sprache: {lang}",
    "bad_units": "Unbekanntes Einheitensystem: {units}",
    "ids_format": "ids muss eine Liste ganzer Zahlen sein",
    "ids_invalid": "ungültige Serien-ID",
    "ids_count": "1 bis {max} Serien angeben",
    "backup_invalid": "Keine gültige LoadLog-Sicherung (Datei beschädigt oder fremd)",
    "backup_too_new": "Die Sicherung stammt aus einer neueren LoadLog-Version (Schema {version}, unterstützt: {supported})",
    "restore_disabled": "Wiederherstellen ist auf diesem Server abgeschaltet (LOADLOG_ALLOW_RESTORE)",
    "restore_confirm": "Zum Wiederherstellen ist die Bestätigung nötig",
    "length_required": "Die Anfrage braucht eine Längenangabe (Content-Length)",
    "cross_site_blocked": "Anfrage von einer fremden Webseite abgewiesen",
    "file_unreadable": "Datei nicht lesbar, übersprungen: {name}",
    "series_number_adjusted": "{label}: Seriennummer aus dem Ordnernamen übernommen (Kopfdaten: {head})",
    "weight_out_of_range": "Das Geschossgewicht der Laborierung liegt außerhalb des zulässigen Bereichs (0,1 bis 100 g)",
    "value_min": "{field}: Wert muss mindestens {limit} sein",
    "value_max": "{field}: Wert darf höchstens {limit} sein",
    "value_length": "{field}: Text zu lang oder zu kurz",
    "value_invalid": "{field}: ungültiger Wert",
    "generic": "{text}",
}


class Note(str):
    """Text (deutsch) mit Code und Parametern; verhält sich überall wie ein normaler String."""

    code: str
    params: dict

    def __new__(cls, code: str, **params):
        template = _DE.get(code, "{text}")
        obj = super().__new__(cls, template.format(**params) if code in _DE else str(params.get("text", code)))
        obj.code = code
        obj.params = params
        return obj

    def as_dict(self) -> dict:
        return {"code": self.code, "message": str(self),
                "params": {k: v.as_dict() if isinstance(v, Note) else v for k, v in self.params.items()}}


class CodedError(ValueError):
    """Fehler mit Meldungscode."""

    def __init__(self, code: str, **params):
        self.note = Note(code, **params)
        super().__init__(str(self.note))


def reason(exc: Exception) -> "Note | str":
    """Grund einer verschachtelten Ausnahme als Meldung (oder Text)."""
    return exc.note if isinstance(exc, CodedError) else str(exc)


def note_json(item: object) -> dict:
    """Beliebigen Hinweis (Note oder einfacher Text) für die API."""
    return item.as_dict() if isinstance(item, Note) else {"code": "generic", "message": str(item), "params": {"text": str(item)}}
