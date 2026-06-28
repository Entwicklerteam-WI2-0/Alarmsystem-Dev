# run-local.ps1 - laedt .env und startet das G2-Backend lokal (Live-Test).
#
# Hintergrund: Die App liest DB_HOST & Co. aus der Prozess-Umgebung (kein load_dotenv im Code).
# Ohne gesetzte Variablen antwortet /v1/assessment/current mit "503: Umgebungsvariable fehlt: DB_HOST".
# Dieses Skript laedt die .env in die Umgebung und startet uvicorn.
#
# Aufruf (aus 04-Source-code/ oder per Doppelklick):
#   .\tools\run-local.ps1            # Port 8000
#   .\tools\run-local.ps1 8080       # anderer Port
#
# Voraussetzung: lokale MariaDB laeuft (start-mariadb.bat) und G1-Sim laeuft (tools/g1_sim/).
# Siehe docs/live-test-runbook.md.

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

# .env zeilenweise in die Prozess-Umgebung laden (KEY=VALUE; Kommentarzeilen mit # ueberspringen).
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        Set-Item -Path ("env:" + $matches[1].Trim()) -Value $matches[2].Trim()
    }
}

# Scheduler fuer den Live-Test scharfschalten (pollt den G1-Sim), falls nicht schon in .env gesetzt.
if (-not $env:G2_ENABLE_SCHEDULER) { $env:G2_ENABLE_SCHEDULER = "true" }

$port = if ($args.Count -ge 1) { $args[0] } else { "8000" }

Write-Host "G2-Backend startet auf :$port  (DB_HOST=$env:DB_HOST, G1=$env:G1_BASE_URL, Scheduler=$env:G2_ENABLE_SCHEDULER)"
Set-Location $srcRoot
& $py -m uvicorn src.main:app --port $port
