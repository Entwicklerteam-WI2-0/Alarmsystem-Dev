#!/usr/bin/env bash
# =============================================================================
# update-pi.sh -- Backend auf dem Pi NICHT-DESTRUKTIV aktualisieren
# =============================================================================
# Bringt das Repo auf den neuesten Stand und uebernimmt ALLE Code-Aenderungen
# (neue Features, Refactorings, Bugfixes) per git pull. Aktualisiert die venv
# nur wenn sich die Abhaengigkeiten geaendert haben und zieht ein geaendertes
# DB-Schema idempotent nach -- OHNE Daten zu loeschen. Danach Service-Neustart.
#
# Unterschied zu setup-pi.sh:
#   setup-pi.sh  = ERSTES Aufsetzen, DROPT die Datenbank (destruktiv).
#   update-pi.sh = laufende Updates, DB + .env bleiben UNVERAENDERT.
#
# Aufruf (aus 04-Source-code/):  ./tools/update-pi.sh
# Beendet bei Problemen mit klarer Meldung; aenderbare Schritte sind No-ops,
# wenn nichts zu tun ist (deps/Schema unveraendert).
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="alarmsystem"
DB_NAME="alarmsystem"
SCHEMA_FILE="migrations/schema.sql"
GRANTS_FILE="migrations/grants.sql"
REQ_FILE="requirements.txt"
VENV_PIP="$PROJECT_DIR/.venv/bin/pip"

log() { echo -e "\n[update] $*"; }
err() { echo -e "\n[update][ERROR] $*" >&2; }

cd "$PROJECT_DIR"

# Vorbedingung: venv vorhanden -> dies ist ein UPDATE, kein Erst-Setup.
if [[ ! -x "$VENV_PIP" ]]; then
    err "venv fehlt ($VENV_PIP). Dies ist ein Update-Skript -- erst ./tools/setup-pi.sh ausfuehren."
    exit 1
fi

MYSQL="mysql"
command -v mariadb &>/dev/null && MYSQL="mariadb"

hash_of() { sha256sum "$1" 2>/dev/null | awk '{print $1}' || echo "absent"; }

# --- 1) Stand der versionierten Inputs VOR dem Pull merken -------------------
req_before=$(hash_of "$REQ_FILE")
schema_before=$(hash_of "$SCHEMA_FILE")
grants_before=$(hash_of "$GRANTS_FILE")

# --- 2) Code holen (alle Code-Aenderungen) ----------------------------------
log "Hole neuesten Code (git pull --ff-only) ..."
if ! git pull --ff-only; then
    err "git pull fehlgeschlagen (lokale Aenderungen/Divergenz auf dem Pi?)."
    err "Pruefe:  git status   |   lokale Aenderungen verwerfen:  git stash"
    exit 1
fi

req_after=$(hash_of "$REQ_FILE")
schema_after=$(hash_of "$SCHEMA_FILE")
grants_after=$(hash_of "$GRANTS_FILE")

# --- 3) Abhaengigkeiten nur bei Bedarf aktualisieren ------------------------
if [[ "$req_before" != "$req_after" ]]; then
    log "requirements.txt hat sich geaendert -> Abhaengigkeiten aktualisieren ..."
    "$VENV_PIP" install -r "$REQ_FILE"
else
    log "requirements.txt unveraendert -> kein pip-Lauf noetig."
fi

# --- 4) DB-Schema + Rechte nur bei Bedarf nachziehen (idempotent, NICHT-destruktiv) ---
# schema.sql und grants.sql werden gemeinsam behandelt: aendert sich schema.sql,
# muss grants.sql zwingend neu laufen (DTB-54 -- neue Tabellen brauchen Rechte,
# sonst scheitert die App mit "Access denied"). grants.sql allein (ohne schema-
# Aenderung) wird separat gezogen. Beide Skripte sind idempotent.
if [[ "$schema_before" != "$schema_after" ]]; then
    log "schema.sql hat sich geaendert -> wird idempotent nachgezogen (Daten bleiben erhalten)."
    # schema.sql ist idempotent (CREATE TABLE IF NOT EXISTS + INFORMATION_SCHEMA-Checks).
    # DDL braucht Root-Rechte -> sudo nutzt die unix_socket-Auth (frischer Pi: kein PW noetig).
    if ! sudo "$MYSQL" "$DB_NAME" < "$SCHEMA_FILE"; then
        err "Schema-Migration fehlgeschlagen (Root-DB-Zugang noetig?)."
        err "Manuell nachziehen:  sudo $MYSQL $DB_NAME < $SCHEMA_FILE   (ggf. -p fuer Root-PW)"
        exit 1
    fi
    # Neue Tabellen -> Rechte fuer den App-User fehlen sonst. grants.sql ist idempotent.
    log "schema.sql geaendert -> grants.sql neu einspielen (App-User-Rechte, DTB-54)."
    if ! sudo "$MYSQL" "$DB_NAME" < "$GRANTS_FILE"; then
        err "GRANT-Refresh fehlgeschlagen (Root-DB-Zugang noetig?)."
        err "Manuell:  sudo $MYSQL $DB_NAME < $GRANTS_FILE   (ggf. -p fuer Root-PW)"
        exit 1
    fi
elif [[ "$grants_before" != "$grants_after" ]]; then
    log "grants.sql hat sich geaendert -> Rechte-Matrix wird neu eingespielt (idempotent)."
    if ! sudo "$MYSQL" "$DB_NAME" < "$GRANTS_FILE"; then
        err "GRANT-Refresh fehlgeschlagen (Root-DB-Zugang noetig?)."
        err "Manuell:  sudo $MYSQL $DB_NAME < $GRANTS_FILE   (ggf. -p fuer Root-PW)"
        exit 1
    fi
else
    log "schema.sql + grants.sql unveraendert -> keine DB-Migration noetig."
fi

# --- 5) Service neu starten + Health-Check ----------------------------------
log "Starte Service '$SERVICE_NAME' neu ..."
sudo systemctl restart "$SERVICE_NAME"
for _ in 1 2 3 4 5; do
    sleep 1
    sudo systemctl is-active --quiet "$SERVICE_NAME" && break
done
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    IP=$(hostname -I | awk '{print $1}')
    log "Update abgeschlossen -- Backend laeuft."
    log "Health-Check:  curl http://${IP:-localhost}:8000/v1/health"
else
    err "Backend startet nach dem Update nicht. Details:  sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi
