# Pi-Deploy — G2-Backend vor Ort live bringen (echter G1 + G3)

> **Zweck:** Das G2-Backend auf einem Raspberry Pi (Linux/ARM) gegen den **echten G1-Sensor** und das
> **G3-Frontend** in Betrieb nehmen. Für die Vor-Ort-Integration (M3, DTB-17/23).
>
> **Verwandte Doku (maßgeblich):** DB-Setup → [`dev-db-setup.md`](dev-db-setup.md) (Schnellstart B = Linux,
> Source of Truth für DB) · lokaler Sim-Test → [`live-test-runbook.md`](live-test-runbook.md) §6 ·
> Agenten-Test → [`agent-live-test-manual.md`](agent-live-test-manual.md) §8 (Env-Umstellung Sim → echter G1).
>
> **Annahme:** MariaDB läuft mit auf dem Pi; das Backend soll im Intranet für G3 erreichbar sein.
> **Unterschied zum lokalen Sim-Test:** kein G1-Sim — `G1_BASE_URL` zeigt auf den **echten** G1.
> Der erprobte Ablauf (native MariaDB → `schema.sql` → `grants.sql` → `.env` → `uvicorn`) stammt aus dem
> STOA-Real-Test (2026-06-28).

---

## 0. Voraussetzungen

- Raspberry Pi OS / Debian, SSH-Zugang.
- **Von G1 (Nils):** die erreichbare G1-Adresse, z. B. `http://g1-sensorik.local` oder `http://<g1-ip>:<port>`.
- **Von G3 (Nick):** die Origin des Frontends (Host:Port), z. B. `http://<g3-host>:3000`.
- Den Code (`Alarmsystem-Dev`) auf dem Pi (git clone oder rsync).

## 1. Code + Python-Umgebung

```bash
cd ~/Alarmsystem-Dev/04-Source-code
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Laufzeit-Deps (nicht -dev)
```

## 2. MariaDB installieren + DB/User (siehe `dev-db-setup.md` Schnellstart B)

```bash
sudo apt-get install -y mariadb-server
sudo systemctl enable --now mariadb
# DB + zwei User. 'app' = Setup/Schema (alle Rechte); 'alarm' = App-Laufzeit (least-priv, NF-09):
sudo mariadb -e "CREATE DATABASE IF NOT EXISTS alarmsystem CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mariadb -e "CREATE USER IF NOT EXISTS 'app'@'%'   IDENTIFIED BY '<setup-pw>'; GRANT ALL ON *.* TO 'app'@'%' WITH GRANT OPTION;"
sudo mariadb -e "CREATE USER IF NOT EXISTS 'alarm'@'%' IDENTIFIED BY '<app-pw>';"
sudo mariadb -e "FLUSH PRIVILEGES;"
```

## 3. Schema + Least-Privilege-Rechte einspielen

```bash
cd ~/Alarmsystem-Dev/04-Source-code
mariadb -h127.0.0.1 -P3306 -u app -p alarmsystem < migrations/schema.sql
mariadb -h127.0.0.1 -P3306 -u app -p alarmsystem < migrations/grants.sql
```

> ⚠️ **Gotcha (`dev-db-setup.md`):** `grants.sql` adressiert `'alarm'@'localhost'`. Da die App per TCP
> (`127.0.0.1`) verbindet, muss der User als **`'alarm'@'%'`** existieren (Schritt 2 erledigt das) — sonst
> `ERROR 1142 ... command denied`. Ggf. die Host-Specifier in `grants.sql` vor dem Einspielen von
> `localhost` → `%` anpassen.

> 🔁 **Upgrade einer BESTEHENDEN DB (Schema-Änderung — z. B. neue Spalte `reading.wind_speed_ms`):**
> `schema.sql` ist **idempotent** (`CREATE TABLE IF NOT EXISTS` + bedingte `ALTER`-Migrationen via
> `INFORMATION_SCHEMA`). Wenn ein `git pull` das Schema ändert, `schema.sql` **vor dem Service-Neustart
> erneut einspielen** — sonst scheitern alle `INSERT`s mit `Unknown column` und es wird **nichts
> persistiert** (die Pipeline läuft fail-safe auf `unknown`, aber die Demo steht). Re-Apply ist gefahrlos:
> ```bash
> cd ~/Alarmsystem-Dev/04-Source-code
> mariadb -h127.0.0.1 -P3306 -u app -p alarmsystem < migrations/schema.sql
> sudo systemctl restart alarm-backend   # falls als Service (Schritt 7)
> ```

## 4. `.env` anlegen (echte Werte — wird nie committet, NF-07)

```bash
cp .env.example .env
nano .env
```

Für den **Live-Betrieb** setzen:

```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=alarmsystem
DB_USER=alarm                           # Laufzeit = least-priv (NICHT 'app')
DB_PASSWORD=<app-pw>
G1_BASE_URL=http://<echte-g1-adresse>   # von Nils (Code-Default: http://g1-sensorik.local)
G2_ENABLE_SCHEDULER=true                # SCHARF — sonst pollt nichts (Dauer-503)
G2_API_KEY=<sicheres-zufalls-secret>    # z. B. `openssl rand -hex 32`
G2_CORS_ORIGINS=http://<g3-host>:3000   # Origin des G3-Frontends, statt Wildcard
```

| Env | lokaler Sim-Test | Vor-Ort / echter G1 |
|---|---|---|
| `G1_BASE_URL` | `http://127.0.0.1:9101` (Sim) | echter G1-Endpoint (per Seam-Sync) |
| `G2_CORS_ORIGINS` | ungesetzt → `*` | **Origin des G3-Frontends** |
| `G2_API_KEY` | lokaler Dev-Key | echter Key (ohne → Schreibzugriff `503`, fail-safe-closed) |
| `G2_ENABLE_SCHEDULER` | `true` | `true` (Scheduler scharf) |

## 5. Backend starten — im Netz erreichbar

> Der Code lädt `.env` **nicht** selbst. Erst in die Prozess-Umgebung laden, dann starten. `--host 0.0.0.0`
> macht es für G3 im Intranet erreichbar (lokal genügt `127.0.0.1`):

```bash
cd ~/Alarmsystem-Dev/04-Source-code
set -a; . ./.env; set +a
.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## 6. Verifizieren

```bash
# auf dem Pi:
curl -s http://127.0.0.1:8000/v1/health               # {"status":"ok"}
curl -s http://127.0.0.1:8000/v1/assessment/current   # risk_level + Messwerte (echte G1-Daten)
hostname -I                                            # Pi-IP merken
# von G3/anderem Gerät im selben Netz:
#   http://<pi-ip>:8000/v1/assessment/current   und   http://<pi-ip>:8000/docs
```

Beim Start steht im Log `Kein threshold_set in der DB -> JSON-Seed-Config (config/thresholds.json)` — das ist
**normal** (Fallback auf die JSON-Schwellen). Kommt Dauer-`503`: meist `G2_ENABLE_SCHEDULER` aus oder G1 nicht
erreichbar — Server-Log prüfen.

## 7. Dauerhaft laufen lassen (systemd — überlebt Logout/Reboot)

`/etc/systemd/system/alarm-backend.service`:

```ini
[Unit]
Description=G2 Alarmsystem Backend
After=network.target mariadb.service

[Service]
WorkingDirectory=/home/pi/Alarmsystem-Dev/04-Source-code
EnvironmentFile=/home/pi/Alarmsystem-Dev/04-Source-code/.env
ExecStart=/home/pi/Alarmsystem-Dev/04-Source-code/.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now alarm-backend
sudo journalctl -u alarm-backend -f      # Live-Log
```

> `EnvironmentFile=.env` lädt die Variablen automatisch — kein `set -a` mehr nötig.

---

## Stolperfallen (die dich vor Ort treffen)

1. **Dauer-`503`** → `G2_ENABLE_SCHEDULER=true` vergessen **oder** `G1_BASE_URL` falsch / G1 nicht erreichbar.
2. **`ERROR 1142 ... denied`** → `alarm`-User als `@'localhost'` statt `@'%'` (TCP-Falle, siehe Schritt 3).
3. **G3 sieht nichts / CORS-Fehler im Browser** → `G2_CORS_ORIGINS` fehlt/falsch, oder `--host 0.0.0.0` vergessen.
4. **`Unknown column` / nach einem Update wird nichts mehr persistiert** → Schema-Änderung nicht eingespielt; `schema.sql` auf der bestehenden DB **erneut** ausführen (idempotent), dann Service neu starten (Schritt 3).

## Sicherheit

- **TLS** terminiert laut Konzept ein **Reverse-Proxy**, nicht die App (NF-07). Im abgeschlossenen Intranet
  ist HTTP für die Integration akzeptabel.
- **G1 bleibt HTTP** (eingefrorene Naht, HTTP-only). Erst wenn G1 ein Zertifikat bereitstellt:
  `G1_BASE_URL=https://...` — **per Env**, nicht im Code erzwingen.
- **RB-01:** Das System ist reine Entscheidungsunterstützung — kein Aktor, keine Bahn-Freigabe/-Sperre.

---

*Stand: 2026-06-29 · Bezug: DTB-17/23 (G1/G3-Integration), STOA-Real-Test (28.06.), NF-01/NF-07/RB-01.
Lebendes Dokument — bei Setup-/Stack-/Contract-Änderung nachziehen.*
