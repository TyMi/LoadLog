"""Texte für Berichte und Diagramme (Deutsch/Englisch)."""

from .messages import CodedError

LANGS = ("de", "en")

_DE = {
    "app": "LoadLog", "page": "Seite", "of": "von", "created": "Erstellt",
    "series": "Serie", "series_pl": "Serien", "shot": "Schuss", "shots": "Schüsse",
    "avg": "Mittelwert", "sd": "Standardabweichung", "es": "Extreme Spread", "minmax": "Min–Max",
    "date": "Datum", "energy": "Ø Energie", "impulse": "Ø Impuls (MIP)", "impulse_min": "min.", "impulse_col": "MIP", "bc": "Ø BC", "bc_note": "BC aus der Geschwindigkeitsabnahme (lb/in², ICAO-Standardatmosphäre), Schüsse ohne ausreichende Messstrecke ausgenommen.", "counted": "gewertet", "excluded": "Ausgeschlossen", "included": "Gewertet",
    "signal": "Signal", "time": "Zeit", "status": "Status", "note": "Notiz", "group": "Gruppengröße", "device": "Gerät",
    "load": "Laborierung", "loads": "Laborierungen", "weapon": "Waffe", "trial": "Versuchsart",
    "trial_single": "Einzelmessung", "trial_ladder": "Ladeleiter", "trial_seating": "Setztiefen-Test",
    "head_data": "Stammdaten", "powder": "Pulver", "charge": "Menge", "case": "Hülse",
    "firings": "Abfeuerungen", "trim": "Trimmlänge", "primer": "Zünder", "bullet": "Geschoss",
    "bullet_weight": "Geschossgewicht", "lot": "Charge", "coal": "Gesamtlänge", "seating": "Setztiefe",
    "seating_ref": "Bezug", "crimp": "Krimp", "temperature": "Temperatur", "caliber": "Kaliber",
    "barrel": "Lauflänge", "twist": "Drall", "notes": "Notizen", "name": "Name",
    "velocity": "Geschwindigkeit", "distance": "Distanz", "trend": "Trend", "trend_per_series": "je Serie",
    "track_title": "Geschwindigkeit über Distanz", "strip_title": "V0 je Schuss, Mittelwert und ±1 SD",
    "ladder_title": "V0 über", "compare_title": "Serienvergleich", "report_series": "Serienbericht",
    "report_load": "Laborierungsbericht", "report_compare": "Vergleichsbericht",
    "no_data": "Keine Daten", "open_circle": "Offener Kreis = ausgeschlossen",
    "delta_avg": "Δ Ø", "trigger": "Trigger", "assigned": "Zugeordnet", "load_col": "Laborierung",
    "disclaimer": "Aufzeichnung eigener Messwerte, keine Ladedaten und keine Ladeempfehlung. Ladedaten nur aus aktuellen Herstellerquellen; die Verantwortung liegt beim Wiederlader. Berechnete Werte (Energie, Impuls, BC) sind Näherungen. Bei Doppler-Trigger ist V0 nicht die Mündungsgeschwindigkeit.",
    "aria_track": "Geschwindigkeitsverläufe aller Schüsse der Serie",
    "aria_energy": "Mittlere Energie über die Distanz der Serie mit Streuband",
    "energy_axis": "Energie", "energy_title": "Energie über Distanz",
    "aria_sequence": "V0 über die Schussfolge der Serie mit gleitendem Mittelwert und Trend",
    "moving_avg": "Gleitender Mittelwert ({n} Schüsse)", "trend_per_shot": "je Schuss", "sequence_title": "V0 über die Schussfolge",
    "aria_strip": "V0 aller Schüsse je Serie als Punktewolke mit Mittelwert",
    "aria_ladder": "Mittelwert und Streuung der Serien über dem variierten Wert",
}

_EN = {
    "app": "LoadLog", "page": "Page", "of": "of", "created": "Created",
    "series": "Series", "series_pl": "Series", "shot": "Shot", "shots": "Shots",
    "avg": "Average", "sd": "Std. deviation", "es": "Extreme spread", "minmax": "Min–Max",
    "date": "Date", "energy": "Avg. energy", "impulse": "Avg. impulse (MIP)", "impulse_min": "min.", "impulse_col": "MIP", "bc": "Avg. BC", "bc_note": "BC derived from the velocity decay (lb/in², ICAO standard atmosphere); shots without a sufficient tracked distance are left out.", "counted": "counted", "excluded": "Excluded", "included": "Counted",
    "signal": "Signal", "time": "Time", "status": "Status", "note": "Note", "group": "Group size", "device": "Device",
    "load": "Load", "loads": "Loads", "weapon": "Firearm", "trial": "Trial type",
    "trial_single": "Single measurement", "trial_ladder": "Charge ladder", "trial_seating": "Seating depth test",
    "head_data": "Load data", "powder": "Powder", "charge": "Charge", "case": "Case",
    "firings": "Firings", "trim": "Trim length", "primer": "Primer", "bullet": "Bullet",
    "bullet_weight": "Bullet weight", "lot": "Lot", "coal": "Overall length", "seating": "Seating depth",
    "seating_ref": "Reference", "crimp": "Crimp", "temperature": "Temperature", "caliber": "Caliber",
    "barrel": "Barrel length", "twist": "Twist", "notes": "Notes", "name": "Name",
    "velocity": "Velocity", "distance": "Distance", "trend": "Trend", "trend_per_series": "per series",
    "track_title": "Velocity over distance", "strip_title": "V0 per shot, average and ±1 SD",
    "ladder_title": "V0 over", "compare_title": "Series comparison", "report_series": "Series report",
    "report_load": "Load report", "report_compare": "Comparison report",
    "no_data": "No data", "open_circle": "Open circle = excluded",
    "delta_avg": "Δ avg", "trigger": "Trigger", "assigned": "Assigned", "load_col": "Load",
    "disclaimer": "Record of your own measurements, not load data and not a load recommendation. Use load data only from current manufacturer sources; the reloader is responsible. Calculated values (energy, impulse, BC) are approximations. With Doppler trigger, V0 is not the muzzle velocity.",
    "aria_track": "Velocity tracks of all shots in the series",
    "aria_energy": "Mean energy over distance of the series with scatter band",
    "energy_axis": "Energy", "energy_title": "Energy over distance",
    "aria_sequence": "V0 over the shot sequence of the series with moving average and trend",
    "moving_avg": "Moving average ({n} shots)", "trend_per_shot": "per shot", "sequence_title": "V0 over the shot sequence",
    "aria_strip": "V0 of all shots per series as dot plot with average",
    "aria_ladder": "Average and spread of the series over the varied value",
}

TEXTS = {"de": _DE, "en": _EN}


def check_lang(lang: str) -> str:
    if lang not in LANGS:
        raise CodedError("bad_lang", lang=lang)
    return lang


def t(lang: str, key: str) -> str:
    return TEXTS[lang][key]
