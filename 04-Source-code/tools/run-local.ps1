# run-local.ps1 - laedt .env und startet das G2-Backend lokal fuer den Live-Test.
#
# Hintergrund: Die App liest DB_HOST & Co. aus der Prozess-Umgebung (kein load_dotenv im Code).
# Ohne gesetzte Variablen antwortet /v1/assessment/current mit 503 (DB nicht konfiguriert).
# Dieses Skript laedt die .env in die Umgebung und ERZWINGT die Live-Test-Defaults, damit der
# haeufige Fehlerfall (.env aus .env.example: Scheduler aus, G1 auf Produktiv-Host) nicht
# stillschweigend in ein totes System (Dauer-503) laeuft.
#
# Aufruf (aus 04-Source-code/; ExecutionPolicy-Bypass noetig, da .ps1 default blockiert):
#   powershell -ExecutionPolicy Bypass -File .\tools\run-local.ps1          # Port 8000
#   powershell -ExecutionPolicy Bypass -File .\tools\run-local.ps1 8080     # anderer Port
#
# Voraussetzung: lokale MariaDB laeuft (siehe docs/dev-db-setup.md) und der G1-Sim laeuft
# (python tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json).

$ErrorActionPreference = "Stop"

$srcRoot = Split-Path -Parent $PSScriptRoot   # tools/ -> 04-Source-code/
$envFile = Join-Path $srcRoot ".env"
$py      = Join-Path $srcRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $envFile)) {
    Write-Error ".env fehlt ($envFile). Aus .env.example anlegen und DB-Zugang eintragen."
    exit 1
}
if (-not (Test-Path $py)) {
    Write-Error "venv fehlt. Erst: py -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
    exit 1
}

# .env zeilenweise in die Prozess-Umgebung laden:
#  - Kommentarzeilen (#) und Leerzeilen ueberspringen
#  - '=' im Wert bleibt erhalten (Gruppe 2 ist gierig)
#  - umschliessende einfache/doppelte Anfuehrungszeichen entfernen (dotenv-Gewohnheit)
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim() -replace '^["'']|["'']$', ''
        Set-Item -Path ("env:" + $key) -Value $val
    }
}

# --- Live-Test-Defaults ERZWINGEN (Schutz gegen die .env.example-Defaults) ---
# Scheduler MUSS an sein, sonst pollt das Backend den G1-Sim nie (-> Dauer-503).
# Bewusst hart gesetzt: dieses Skript dient ausschliesslich dem lokalen Live-Test.
$env:G2_ENABLE_SCHEDULER = "true"
# G1 MUSS auf den lokalen Sim zeigen. .env.example defaultet auf den Produktiv-Host
# (g1-sensorik.local); ist nichts oder dieser Default gesetzt, auf den Sim umbiegen.
if ([string]::IsNullOrWhiteSpace($env:G1_BASE_URL) -or $env:G1_BASE_URL -like "*g1-sensorik*") {
    $env:G1_BASE_URL = "http://127.0.0.1:9101"
}

$port = if ($args.Count -ge 1) { $args[0] } else { "8000" }

Write-Host "G2-Backend startet auf :$port  (DB_HOST=$env:DB_HOST, G1=$env:G1_BASE_URL, Scheduler=$env:G2_ENABLE_SCHEDULER)"
Set-Location $srcRoot
& $py -m uvicorn src.main:app --port $port
