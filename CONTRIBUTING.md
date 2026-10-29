# Mitwirken

- Issues und Pull Requests sind willkommen. Vor größeren Änderungen bitte ein Issue
  zur Abstimmung anlegen.
- Keine echten Zugangsdaten, Tokens, IPs oder personenbezogenen Messdaten committen.
  CI prüft per `gitleaks` auf Secrets.
- **Beispieldaten nur synthetisch** erzeugen (`backend/src/loadlog/synth.py`), keine
  geschwärzten Originale. Das gilt auch für Test-Fixtures und Screenshots.
- Vor einem PR: `uv run pytest && uv run ruff check src tests` (in `backend/`) sowie
  `npm test && npm run typecheck` (in `frontend/`).
- Texte der Oberfläche liegen in `frontend/src/i18n.ts` (Deutsch und Englisch müssen
  dieselben Schlüssel haben, ein Test prüft das), Berichtstexte in `backend/src/loadlog/i18n.py`,
  das Handbuch in `docs/manual/de|en`.
- Mit einem Pull Request bestätigst du, dass du die Rechte an deinem Beitrag hast und ihn unter der MIT-Lizenz dieses Projekts
  bereitstellst (*inbound = outbound*). Ein Contributor License Agreement gibt es nicht.
