# ──────────────────────────────────────────────────────────────
# setup.ps1 — Einmal-Setup für G2 (Windows / PowerShell)
# Aufruf:  powershell -ExecutionPolicy Bypass -File setup.ps1
# Macht:   uv sicherstellen -> Python-Umgebung -> CLAUDE.md aus claude-sync.md
# ──────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
Write-Host "G2-Setup startet in: $(Get-Location)"

# 1) uv sicherstellen
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv nicht gefunden - installiere uv ..."
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
} else {
    Write-Host "uv vorhanden ($(uv --version))"
}

# 2) Python-Umgebung + Abhaengigkeiten
Write-Host "Installiere Python-Umgebung (uv sync) ..."
uv sync

# 3) Gemeinsame Agent-Config lokal aktivieren
if (-not (Test-Path CLAUDE.md)) {
    Copy-Item claude-sync.md CLAUDE.md
    Write-Host "CLAUDE.md aus claude-sync.md erstellt"
} else {
    Write-Host "CLAUDE.md existiert bereits - bleibt unangetastet."
    Write-Host "(Regeln aktualisieren? -> 'Copy-Item claude-sync.md CLAUDE.md' nach 'git pull')"
}

Write-Host ""
Write-Host "Fertig. Naechste Schritte:"
Write-Host "  1) Ordner in VS Code oeffnen"
Write-Host "  2) 'claude' im integrierten Terminal starten"
Write-Host "  3) Projekt einmal 'vertrauen', dann '/start' tippen"
