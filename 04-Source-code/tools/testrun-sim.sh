#!/usr/bin/env bash
# =============================================================================
# testrun-sim.sh -- G2-Backend gegen den G1-SIMULATOR starten (Testlauf)
# =============================================================================
# Zweck: Backend testen/kalibrier-trocken laufen lassen, wenn die ECHTEN
#        G1-Sensoren nicht verfuegbar sind (z. B. G1-Team nicht da). Startet den
#        G1-Simulator + das Backend und biegt G1_BASE_URL auf den Sim um.
#
# WICHTIG -- aendert NICHTS am Normalbetrieb:
#   - Die .env-Datei bleibt unveraendert (echte G1 192.168.1.22 bleibt drin).
#   - Der systemd-Service wird NICHT angefasst.
#   Der Sim-Override (G1 -> 127.0.0.1, Scheduler an) gilt nur in DIESEM Prozess.
#   Normalbetrieb laeuft weiter ueber:  sudo systemctl start alarmsystem
#
# Aufruf (aus 04-Source-code/):
#   ./tools/testrun-sim.sh            # Backend :8000, Sim :9101
#   ./tools/testrun-sim.sh 8080       # Backend auf anderem Port
#
# Voraussetzung: ./tools/setup-pi.sh wurde einmal ausgefuehrt (venv + .env + DB).
# Beenden: Strg+C -> stoppt Backend UND Simulator.
# =============================================================================

set -euo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$SRC_ROOT/.env"
VENV_PY="$SRC_ROOT/.venv/bin/python"
SIM_DIR="$SRC_ROOT/tools/g1_sim"
SIM_STATE="$SIM_DIR/g1_state.json"
SIM_EXAMPLE="$SIM_DIR/g1_state.example.json"
SIM_PORT=9101
BACKEND_PORT="${1:-8000}"

log() { echo -e "\n[testrun] $*"; }
err() { echo -e "\n[testrun][ERROR] $*" >&2; }

# --- Vorbedingungen -----------------------------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
    err ".env fehlt ($ENV_FILE). Erst ./tools/setup-pi.sh ausfuehren."
    exit 1
fi
if [[ ! -x "$VENV_PY" ]]; then
    err "venv fehlt ($VENV_PY). Erst ./tools/setup-pi.sh ausfuehren."
    exit 1
fi

# Normalbetrieb-Service darf nicht gleichzeitig laufen (Port-Konflikt + zwei Backends).
if systemctl is-active --quiet alarmsystem 2>/dev/null; then
    err "Der systemd-Service 'alarmsystem' laeuft (belegt :8000, pollt die ECHTE G1)."
    err "Fuer den Sim-Testrun erst stoppen:   sudo systemctl stop alarmsystem"
    err "Nach dem Test Normalbetrieb zurueck:  sudo systemctl start alarmsystem"
    exit 1
fi

# --- .env in die Prozess-Umgebung laden (App liest aus os.environ) ------------
# Kommentar-/Leerzeilen ueberspringen; umschliessende Quotes + evtl. CR entfernen.
while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"; key="${key// /}"
    [[ -z "$key" ]] && continue
    val="${line#*=}"
    val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
    export "$key=$val"
done < "$ENV_FILE"

# --- TESTRUN-Override: G1 auf den lokalen Sim, Scheduler an -------------------
# Ueberschreibt die produktiven .env-Werte NUR in diesem Prozess (Datei bleibt unveraendert).
export G1_BASE_URL="http://127.0.0.1:${SIM_PORT}"
export G2_ENABLE_SCHEDULER="true"

# --- G1-Simulator vorbereiten + im Hintergrund starten -----------------------
if [[ ! -f "$SIM_STATE" && -f "$SIM_EXAMPLE" ]]; then
    cp "$SIM_EXAMPLE" "$SIM_STATE"
    log "g1_state.json aus Vorlage angelegt."
fi
log "Starte G1-Simulator auf :$SIM_PORT  (State: $SIM_STATE)"
"$VENV_PY" "$SIM_DIR/g1_sim.py" --port "$SIM_PORT" --state "$SIM_STATE" &
SIM_PID=$!

# Sim beim Beenden (Strg+C / exit) sauber stoppen.
cleanup() {
    log "Stoppe G1-Simulator (PID $SIM_PID)."
    kill "$SIM_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 1   # Sim kurz hochfahren lassen

log "G2-Backend startet auf :$BACKEND_PORT  (DB_HOST=${DB_HOST:-?}, G1=$G1_BASE_URL, Scheduler=$G2_ENABLE_SCHEDULER)"
log "Pruefen:           curl http://127.0.0.1:$BACKEND_PORT/v1/assessment/current"
log "Szenario wechseln: $SIM_STATE editieren (Sim liest pro Request neu; Sprung-Guard beachten)."
cd "$SRC_ROOT"
exec "$VENV_PY" -m uvicorn src.main:app --host 0.0.0.0 --port "$BACKEND_PORT"
