---
description: Einmal-Setup der Entwicklungsumgebung (uv, Python, CLAUDE.md)
---
Du richtest die Arbeitsumgebung für dieses Repo ein und führst den Nutzer dabei auf **Deutsch**.

Gehe so vor:
1. **OS erkennen.** macOS/Linux → `bash setup.sh`. Windows → `powershell -ExecutionPolicy Bypass -File setup.ps1`.
2. **Skript ausführen.** Es installiert `uv` (falls nötig), baut die Python-Umgebung (`uv sync`) und legt `CLAUDE.md` aus `claude-sync.md` an.
3. **Verifizieren:** `uv --version` · `uv run python -c "import fastapi, pydantic"` · prüfen, dass `CLAUDE.md` existiert.
4. **Knapp melden**, was passiert ist, und die nächsten Schritte: `claude` neu starten und `/start` tippen.

Bei Fehlern: den Fehler verständlich erklären und den nächsten konkreten Schritt vorschlagen.
Installiere **nichts** heimlich außerhalb des Setup-Skripts. Keine destruktiven Git-Aktionen.
