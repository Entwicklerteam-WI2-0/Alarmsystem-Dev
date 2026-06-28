# Pi-Setup — Datenbank + Backend deployen (G2 Vereisungserkennung)

> Ziel: Das G2-Backend morgen **auf dem Raspberry Pi** ans Laufen bringen — MariaDB,
> Schema, Rechte, `.env`, Start, Verbindungs-Check. Schritt für Schritt abarbeitbar.
> Ergänzt `Raspberry-Pi-Hosting-Anleitung.md` (die deckt „Pi ins Netz / SSH / VS Code / Dauerbetrieb" ab).
>
> **Namens-Entscheidung (wichtig):** Wir nutzen die **Code-Namen** `DB_NAME=alarmsystem` /
> `DB_USER=alarm` — exakt so wie sie in `migrations/grants.sql`, `.env.example`, den Tests und den
> Runbooks (`docs/dev-db-setup.md`, `docs/live-test-runbook.md`) bereits stehen. So muss **keine
> Code-/Testdatei** angefasst werden. Der frühere Pi-User `anr_app`/`vereisung` wird durch `alarm`
> ersetzt (optionaler Cleanup in Schritt 8).

## Eckdaten

| | Wert |
|---|---|
| Hostname (SSH/mDNS) | `icedetection.local` (oder IP, s. u.) |
| IP (falls `.local` nicht geht) | per Router-DHCP / `hostname -I` auf dem Pi prüfen |
| Pi-Benutzer (SSH) | `pi` |
| **Datenbank** | **`alarmsystem`** |
| **DB-Benutzer (App)** | **`alarm`@`127.0.0.1`** (darf nur `alarmsystem`, Least-Privilege) |
| **DB-Passwort** | im **Team-Passwort-Manager** — **NIE ins Git** |
| WLAN-/SSH-Zugang | im **Team-Passwort-Manager** |
| ENV-Vorlage (im Repo) | `04-Source-code/.env.example` |
| ENV-Datei (lokal auf dem Pi, gitignored) | `04-Source-code/.env` |

> Voraussetzung: Laptop und Pi im **selben Netz**; MariaDB läuft auf dem Pi
> (Installation s. `Raspberry-Pi-Hosting-Anleitung.md` bzw. Anhang B unten).

---

## 1. Auf den Pi verbinden (SSH)

```bash
ssh pi@icedetection.local      # oder: ssh pi@<pi-ip>
```
**VS Code:** Extension „Remote - SSH" → `F1` → „Remote-SSH: Connect to Host" → `pi@icedetection.local`.

---

## 2. Code auf den Pi holen / aktualisieren

Im VS-Code-Remote-Terminal (auf dem Pi):

```bash
# Erstes Mal:
git clone <repo-url>
cd Alarmsystem-Dev/04-Source-code
# Bei Updates stattdessen:  git pull

# Virtuelle Umgebung + Abhängigkeiten (Python >= 3.12):
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" "pymysql>=1.1" "httpx>=0.27" "pydantic>=2.0"
```

> Alle weiteren Befehle gehen vom Ordner **`04-Source-code/`** aus.

---

## 3. Datenbank + App-User anlegen (einmalig, als DB-Admin)

```bash
sudo mariadb        # interaktive root-Konsole (vermeidet Heredoc-Fallen)
```
```sql
CREATE DATABASE IF NOT EXISTS alarmsystem CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Host '127.0.0.1', NICHT 'localhost': PyMySQL verbindet per TCP. Ein reiner
-- @'localhost'-Account (= Socket) würde sonst NICHT matchen -> ERROR 1142.
CREATE USER IF NOT EXISTS 'alarm'@'127.0.0.1' IDENTIFIED BY 'DAS_ECHTE_PASSWORT';
EXIT;
```

> Das Passwort hier ist ein **Platzhalter** — echtes PW aus dem Passwort-Manager einsetzen, nicht committen.

---

## 4. Schema + Rechte einspielen (Reihenfolge zwingend: ERST Schema, DANN Grants)

```bash
# 4a) Tabellen anlegen (idempotent):
sudo mariadb alarmsystem < migrations/schema.sql

# 4b) Least-Privilege-Rechte (append-only, NF-09) vergeben.
#     grants.sql ist auf 'alarm'@'localhost' verdrahtet; wir mappen den Host beim
#     Einspielen on-the-fly auf '127.0.0.1' (passt zur TCP-Verbindung) -> migrations/grants.sql
#     im Repo bleibt UNVERÄNDERT. --force: harmlose REVOKE-Hinweise auf frischem User überspringen.
sed "s/'alarm'@'localhost'/'alarm'@'127.0.0.1'/g" migrations/grants.sql | sudo mariadb --force alarmsystem
```

**Verifikation (als Admin):**
```bash
sudo mariadb -e "SHOW GRANTS FOR 'alarm'@'127.0.0.1';"
# Muss INSERT/SELECT (+ UPDATE auf alarm) je Tabelle zeigen — KEIN 'ALL PRIVILEGES'.
```

> **Negativ-Test (muss scheitern, beweist append-only):**
> `mariadb -h127.0.0.1 -u alarm -p alarmsystem -e "UPDATE audit_log SET actor='x' WHERE id=1;"`
> → erwartet **ERROR 1142** (kein UPDATE-Recht). Das ist gewollt.

---

## 5. `.env` auf dem Pi anlegen (lokal, gitignored)

```bash
cp .env.example .env
nano .env        # oder im VS-Code-Editor öffnen
```
Diese Werte setzen (Rest aus `.env.example` kann bleiben):
```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=alarmsystem
DB_USER=alarm
DB_PASSWORD=DAS_ECHTE_PASSWORT     # aus dem Passwort-Manager, NICHT committen
```

> Die App liest die DB-Zugangsdaten **ausschließlich** aus diesen Variablen (NF-07). Es gibt
> **keinen** `.env`-Autoloader im Code — deshalb wird die Datei beim Start explizit übergeben (Schritt 6).

---

## 6. Backend starten

```bash
.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --env-file .env
```

- `--host 0.0.0.0` → die **API** ist von anderen Geräten im Netz erreichbar (für G3/Tests). Die
  **DB** bleibt davon unberührt auf `127.0.0.1` (Merksatz: **„DB zu, API offen"**).
- `--env-file .env` → uvicorn lädt die Variablen in die Umgebung (der Code tut das nicht selbst).
- Zum Entwickeln optional `--reload` ergänzen (lädt bei Code-Änderungen neu).

> **Hinweis Scheduler:** In `.env` steht `G2_ENABLE_SCHEDULER=false` (Default). Echte Bewertungen
> entstehen erst, wenn der Scheduler scharf ist **und** G1 erreichbar ist (`G1_BASE_URL`). Ohne G1
> erzeugt er nur `unknown` (Fail-safe, nie GRÜN). Für den reinen DB-Verbindungs-Check unten reicht der Default.

---

## 7. Verbindung prüfen

In einem **zweiten** Terminal (oder vom Laptop mit `<pi-ip>` statt `127.0.0.1`):

```bash
curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/v1/health
#   -> {"status":"ok"} [200]

curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/v1/thresholds
#   -> Schwellenwert-Config [200]   (braucht keine DB)

curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/v1/assessment/current
#   -> solange DB leer: {"code":"SERVICE_UNAVAILABLE",...} [503]  = Fail-safe, KEIN Fehler
```

Bekommst du bei `/v1/health` ein `200`, ist das Backend live und die App läuft. Ein `503` bei
`assessment/current` heißt nur „noch keine Daten", **kein** Verbindungsproblem. Echte
DB-Schreib-/Lesefehler würden im uvicorn-Log auftauchen (z. B. `ERROR 1142` → dann Schritt 4 prüfen).

---

## 8. (Optional) Alten `anr_app` / `vereisung` aufräumen

MariaDB kann mehrere User/DBs parallel haben — **nötig ist das Löschen nicht.** Sauberer ist es aber,
den alten User (hatte `GRANT ALL`) und die alte, ungenutzte DB zu entfernen, damit es **einen**
Least-Privilege-App-User gibt. **Erst prüfen, ob `vereisung` wirklich leer ist:**

```bash
sudo mariadb -e "SELECT table_name FROM information_schema.tables WHERE table_schema='vereisung';"
# Kommt KEINE Zeile zurück -> leer -> Cleanup unten ist sicher.
# Kommen Tabellen mit Daten -> NICHT löschen, erst klären.
```
```sql
-- Nur ausführen, wenn 'vereisung' leer/ungenutzt ist:
DROP USER IF EXISTS 'anr_app'@'localhost';
DROP DATABASE IF EXISTS vereisung;
```

> Löschen ist **destruktiv** und nur durch Neuanlage rückgängig zu machen. Im Zweifel `anr_app`
> einfach liegen lassen — er stört den Betrieb nicht.

---

## 9. Dauerbetrieb (nach erfolgreichem Test)

Damit das Backend nach Logout/Reboot weiterläuft → **systemd-Service** (kein Docker, E-35).
Vorgehen siehe `Raspberry-Pi-Hosting-Anleitung.md` §5. Der Startbefehl im Service ist der aus Schritt 6.

---

## Sicherheits-Regeln (kurz)

- **DB nur lokal** (`127.0.0.1`) — MariaDB nicht auf `0.0.0.0` öffnen. (NF-07)
- **Passwörter nie committen.** Echte Werte im Passwort-Manager / in `.env` (gitignored). Vorlage = `.env.example`.
- **`alarm`** darf nur `alarmsystem` und nur INSERT/SELECT(+UPDATE auf `alarm`) — append-only (NF-09).
- G1/G3 reden mit der **API**, nie direkt mit der DB (RB-01).

## Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| `ERROR 1142` bei App-Queries | User-Host passt nicht zur Verbindung. App nutzt TCP → User muss `@'127.0.0.1'` (oder `@'%'`) sein, und grants.sql mit demselben Host einspielen (Schritt 4b). |
| `Access denied for user 'alarm'` | Falsches PW in `.env` oder User nicht angelegt (Schritt 3). |
| `assessment/current` immer `503` | DB leer (noch keine Bewertung). Erwartet ohne Scheduler/G1 — kein Fehler. |
| `/v1/health` vom Laptop nicht erreichbar | uvicorn mit `--host 0.0.0.0` gestartet? Pi-Firewall/Port 8000 offen? |
| `REVOKE … ERROR 1141/1064` beim Grants-Einspielen | Harmlos auf frischem User; `--force` überspringt (Schritt 4b). |

## Schnellreferenz

| Aktion | Befehl |
|---|---|
| Auf Pi verbinden | `ssh pi@icedetection.local` |
| DB-Konsole (Admin) | `sudo mariadb` |
| DB-Konsole (App) | `mariadb -h 127.0.0.1 -u alarm -p alarmsystem` |
| Schema einspielen | `sudo mariadb alarmsystem < migrations/schema.sql` |
| Rechte einspielen | `sed "s/'alarm'@'localhost'/'alarm'@'127.0.0.1'/g" migrations/grants.sql \| sudo mariadb --force alarmsystem` |
| Rechte prüfen | `sudo mariadb -e "SHOW GRANTS FOR 'alarm'@'127.0.0.1';"` |
| Backend starten | `.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --env-file .env` |
| Health-Check | `curl http://127.0.0.1:8000/v1/health` |

---

## Anhang A — DBeaver vom Laptop (grafisch, optional)

DBeaver tunnelt **durch SSH** → DB bleibt sicher auf dem Pi.
- **Main:** Host `127.0.0.1` · Port `3306` · DB `alarmsystem` · User `alarm` + Passwort
- **SSH:** „Use SSH Tunnel" ✅ · Host `icedetection.local` · User `pi`

## Anhang B — MariaDB von Grund auf (falls noch nicht installiert)

```bash
sudo apt update
sudo apt install -y mariadb-server
sudo systemctl enable --now mariadb
systemctl status mariadb --no-pager        # active (running)?
sudo mariadb-secure-installation
#   unix_socket Y · remove anon Y · disallow root remote Y · remove test-DB Y · reload Y
```
Danach weiter bei **Schritt 3**.
