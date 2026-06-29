#!/usr/bin/env bash
# =============================================================================
# Initiales Pi-Setup für G2-Backend (Prototyp)
# =============================================================================
# Zweck: Einmaliges Aufsetzen des Backends auf einem Raspberry Pi für erste
#        Funktionstests und Lifetests. Das Skript ist bewusst destruktiv-freundlich:
#        bei Schema-Änderungen später kann man DB + venv neu aufsetzen.
#
# Ausführen als User 'pi' (mit sudo-Rechten für MariaDB + systemd):
#   chmod +x tools/setup-pi.sh
#   ./tools/setup-pi.sh
#
# Voraussetzungen:
#   - Raspberry Pi OS (Bookworm oder neuer)
#   - Internetverbindung
#   - MariaDB noch nicht installiert ODER akzeptiert, dass bestehende DB
#     'alarmsystem' und User 'alarm' neu angelegt werden
#
# Sicherheit:
#   - Generiert ein zufälliges App-Passwort und legt es in .env ab.
#   - .env gehört zum .gitignore und wird nie committet.
#   - DB-Root-Passwort wird interaktiv abgefragt (nicht gespeichert).
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Konfiguration
# -----------------------------------------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_NAME="alarmsystem"
DB_USER="alarm"
DB_HOST="localhost"
DB_PORT="3306"
SERVICE_NAME="alarmsystem"
SERVICE_USER="pi"

# -----------------------------------------------------------------------------
# Hilfsfunktionen
# -----------------------------------------------------------------------------
log_info() {
    echo -e "\n[INFO] $*"
}

log_warn() {
    echo -e "\n[WARN] $*"
}

log_error() {
    echo -e "\n[ERROR] $*" >&2
}

check_command() {
    if ! command -v "$1" &>/dev/null; then
        log_error "Befehl '$1' nicht gefunden. Bitte zuerst installieren."
        exit 1
    fi
}

prompt_yes_no() {
    local prompt="$1"
    local response
    while true; do
        read -rp "$prompt (j/N): " response
        case "$response" in
            [Jj]|[Jj][Aa]) return 0 ;;
            [Nn]|[Nn][Ee]|"") return 1 ;;
            *) echo "Bitte 'j' oder 'n' eingeben." ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 1) Python 3.12 prüfen / installieren
# -----------------------------------------------------------------------------
log_info "Schritt 1/8: Python 3.12 prüfen..."

PYTHON_CMD=""
for cmd in python3.12 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$($cmd --version 2>&1 | awk '{print $2}')
        major_minor=$(echo "$version" | cut -d. -f1,2)
        if awk "BEGIN {exit !($major_minor >= 3.12)}"; then
            PYTHON_CMD=$cmd
            log_info "Python $version gefunden ($cmd)."
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    log_warn "Python >= 3.12 nicht gefunden."
    if prompt_yes_no "Python 3.12 über deadsnakes-Repository installieren?"; then
        check_command "apt"
        sudo apt update
        sudo apt install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt update
        sudo apt install -y python3.12 python3.12-venv python3.12-dev
        PYTHON_CMD="python3.12"
    else
        log_error "Ohne Python 3.12 kann das Backend nicht laufen."
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 2) MariaDB installieren / prüfen
# -----------------------------------------------------------------------------
log_info "Schritt 2/8: MariaDB prüfen/installieren..."

if ! command -v mariadb &>/dev/null && ! command -v mysql &>/dev/null; then
    log_warn "MariaDB nicht gefunden."
    if prompt_yes_no "MariaDB-Server installieren?"; then
        sudo apt update
        sudo apt install -y mariadb-server
        sudo systemctl enable mariadb
        sudo systemctl start mariadb
    else
        log_error "Ohne MariaDB kann das Backend nicht laufen."
        exit 1
    fi
else
    log_info "MariaDB/MySQL-Client ist vorhanden."
fi

# Sicherstellen, dass der Server läuft
if ! sudo systemctl is-active --quiet mariadb 2>/dev/null && ! sudo systemctl is-active --quiet mysql 2>/dev/null; then
    log_warn "MariaDB-Service läuft nicht. Starte ihn..."
    sudo systemctl start mariadb || sudo systemctl start mysql
fi

# -----------------------------------------------------------------------------
# 3) Datenbank + App-User anlegen
# -----------------------------------------------------------------------------
log_info "Schritt 3/8: Datenbank '$DB_NAME' und User '$DB_USER' anlegen..."

DB_PASSWORD=$(openssl rand -base64 32 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')

echo "Bitte das MariaDB-Root-Passwort eingeben (bei frischer Installation oft leer):"
read -rsp "MariaDB root-Passwort: " DB_ROOT_PASSWORD
 echo

MYSQL="mysql"
if command -v mariadb &>/dev/null; then
    MYSQL="mariadb"
fi

# Bei leerem Root-Passwort auf frischem Pi: -p ohne Wert -> Enter drücken
if [[ -z "$DB_ROOT_PASSWORD" ]]; then
    MYSQL_AUTH="-u root"
else
    MYSQL_AUTH="-u root -p'$DB_ROOT_PASSWORD'"
fi

sudo bash -c "$MYSQL $MYSQL_AUTH -e \"
DROP DATABASE IF EXISTS \`$DB_NAME\`;
CREATE DATABASE \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
DROP USER IF EXISTS '$DB_USER'@'$DB_HOST';
CREATE USER '$DB_USER'@'$DB_HOST' IDENTIFIED BY '$DB_PASSWORD';
\""

log_info "Datenbank und User angelegt."

# -----------------------------------------------------------------------------
# 4) Schema + Rechte einspielen
# -----------------------------------------------------------------------------
log_info "Schritt 4/8: Schema und Rechte einspielen..."

cd "$PROJECT_DIR"

sudo bash -c "$MYSQL $MYSQL_AUTH $DB_NAME < migrations/schema.sql"
sudo bash -c "$MYSQL $MYSQL_AUTH $DB_NAME < migrations/grants.sql"

log_info "Schema + Rechte eingespielt."

# -----------------------------------------------------------------------------
# 5) Virtuelle Umgebung aufbauen
# -----------------------------------------------------------------------------
log_info "Schritt 5/8: Python-Virtualenv aufbauen..."

cd "$PROJECT_DIR"

if [[ -d ".venv" ]]; then
    if prompt_yes_no "Bestehendes .venv löschen und neu anlegen?"; then
        rm -rf .venv
    fi
fi

if [[ ! -d ".venv" ]]; then
    "$PYTHON_CMD" -m venv .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

log_info "Abhängigkeiten installiert."

# -----------------------------------------------------------------------------
# 6) .env anlegen
# -----------------------------------------------------------------------------
log_info "Schritt 6/8: Laufzeit-Konfiguration (.env) anlegen..."

cd "$PROJECT_DIR"

if [[ -f ".env" ]]; then
    log_warn "Bestehende .env gefunden."
    if ! prompt_yes_no ".env überschreiben? (Alte Credentials gehen verloren!)"; then
        log_info "Behalte bestehende .env."
    else
        mv .env ".env.backup.$(date +%Y%m%d-%H%M%S)"
        create_env=1
    fi
else
    create_env=1
fi

API_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')

if [[ "${create_env:-0}" -eq 1 ]]; then
    cat > .env <<EOF
# Automatisch generiert durch tools/setup-pi.sh am $(date -Iseconds)
# Diese Datei gehört NICHT ins Git.

DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

DB_CONNECT_TIMEOUT=5
DB_AUTOCOMMIT=false
DB_CHARSET=utf8mb4

# G1-Sensor-API (anpassen, sobald G1-Adresse bekannt)
G1_BASE_URL=http://g1-sensorik.local

# Scheduler für Live-Betrieb einschalten
G2_ENABLE_SCHEDULER=true

# Auth-Key für POST /v1/thresholds
G2_API_KEY=$API_KEY

# Frontend (optional; G3-dist separat bauen + Pfad anpassen)
# G2_FRONTEND_DIR=/home/pi/frontend_dist
EOF
    log_info ".env angelegt."
fi

# -----------------------------------------------------------------------------
# 7) Systemd-Service installieren
# -----------------------------------------------------------------------------
log_info "Schritt 7/8: Systemd-Service installieren..."

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Service dynamisch generieren, damit WorkingDirectory/EnvFile immer passen
SERVICE_USER="${SUDO_USER:-$USER}"
if [[ "$SERVICE_USER" == "root" ]]; then
    SERVICE_USER="pi"
fi

if [[ -f "$SERVICE_FILE" ]]; then
    log_warn "Service-Datei existiert bereits."
    if ! prompt_yes_no "Systemd-Service überschreiben?"; then
        log_info "Behalte bestehende Service-Datei."
    fi
fi

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=G2-Backend — Vereisungserkennung ANR
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
log_info "Service '$SERVICE_NAME' aktiviert."

# -----------------------------------------------------------------------------
# 8) App starten
# -----------------------------------------------------------------------------
log_info "Schritt 8/8: Backend starten..."

if prompt_yes_no "Backend jetzt starten?"; then
    sudo systemctl restart "$SERVICE_NAME"
    sleep 2
    if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        log_info "Backend läuft. Status: sudo systemctl status $SERVICE_NAME"
        IP=$(hostname -I | awk '{print $1}')
        log_info "Health-Check: curl http://$IP:8000/v1/health"
    else
        log_error "Backend startet nicht. Details: sudo systemctl status $SERVICE_NAME"
        exit 1
    fi
else
    log_info "Backend nicht gestartet. Manuell starten mit: sudo systemctl start $SERVICE_NAME"
fi

# -----------------------------------------------------------------------------
# Abschluss
# -----------------------------------------------------------------------------
log_info "Setup abgeschlossen."
echo ""
echo "Wichtige Pfade:"
echo "  Projekt:    $PROJECT_DIR"
echo "  Config:     $PROJECT_DIR/.env"
echo "  Service:    sudo systemctl status $SERVICE_NAME"
echo "  Logs:       sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Bei späteren Updates (neues Schema / neue Kernlogik):"
echo "  git pull && rm -rf .venv && ./tools/setup-pi.sh"
echo ""
echo "ACHTUNG: ./tools/setup-pi.sh legt die Datenbank dabei neu an – Daten gehen verloren."
echo "Für späteres Nicht-Destructive-Update bitte ein Upgrade-Skript bauen."
