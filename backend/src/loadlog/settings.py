"""Einstellungen des Servers, die in der Oberfläche änderbar sind (Datei `settings.json` neben der Datenbank).

Sie liegen bewusst nicht in der Datenbank: Eine Wiederherstellung ersetzt die Daten, aber nicht die Einstellungen
dieser Installation.
"""

import json
import os
from pathlib import Path

DEFAULTS = {"backup_keep": 5}
LIMITS = {"backup_keep": (1, 100)}


class Settings:
    def __init__(self, path: Path | None):
        self.path = path
        self._values = dict(DEFAULTS)
        if path is not None and path.is_file():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                stored = {}
            for key, (lo, hi) in LIMITS.items():
                v = stored.get(key) if isinstance(stored, dict) else None
                if isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi:
                    self._values[key] = v

    def get(self) -> dict:
        return dict(self._values)

    def update(self, values: dict) -> dict:
        self._values.update(values)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._values, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)  # ganz oder gar nicht
        return self.get()
