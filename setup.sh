#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# setup.sh — Einmal-Setup für G2 (macOS / Linux)
# Aufruf:  bash setup.sh    (oder ./setup.sh nach chmod +x)
# Macht:   uv sicherstellen → Python-Umgebung → CLAUDE.md aus claude-sync.md
# ──────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")"
echo "▶ G2-Setup startet in: $(pwd)"

# 1) uv (Python-Paket-/Umgebungs-Manager) sicherstellen
if ! command -v uv >/dev/null 2>&1; then
  echo "▶ uv nicht gefunden — installiere uv …"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv landet in ~/.local/bin — für diese Session verfügbar machen
  export PATH="$HOME/.local/bin:$PATH"
else
  echo "✓ uv vorhanden ($(uv --version))"
fi

# 2) Python-Umgebung + Abhängigkeiten (reproduzierbar aus pyproject.toml)
echo "▶ Installiere Python-Umgebung (uv sync) …"
uv sync

# 3) Gemeinsame Agent-Config lokal aktivieren (claude-sync.md → CLAUDE.md)
if [ ! -f CLAUDE.md ]; then
  cp claude-sync.md CLAUDE.md
  echo "✓ CLAUDE.md aus claude-sync.md erstellt"
else
  echo "ℹ CLAUDE.md existiert bereits — lasse sie unangetastet."
  echo "  (Gemeinsame Regeln aktualisieren? -> 'cp claude-sync.md CLAUDE.md' nach 'git pull')"
fi

echo ""
echo "✅ Fertig. Nächste Schritte:"
echo "   1) Ordner in VS Code öffnen"
echo "   2) 'claude' im integrierten Terminal starten"
echo "   3) Projekt einmal 'vertrauen', dann '/start' tippen"
