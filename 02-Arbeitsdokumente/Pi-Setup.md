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
# Erstes Mal (URL aus GitHub kopieren -> Org "Entwicklerteam-WI2-0", Repo "Alarmsystem-Dev"):
git clone https://github.com/Entwicklerteam-WI2-0/Alarmsystem-Dev.git
cd Alarmsystem-Dev/04-Source-code
# Bei Updates stattdessen:  git pull

# Python-Version ZUERST prüfen (Stack braucht >= 3.12!):
python3 --version          # muss 3.12 oder höher zeigen
#   Raspberry Pi OS Bookworm liefert ab Werk nur Python 3.11 -> dann python3.12 nachinstallieren
#   (z. B. via pyenv) und unten 'python3' durch 'python3.12' ersetzen. Sonst ist die >=3.12-
#   Anforderung still NICHT erfüllt und es kracht erst später.
#
#   pyenv-Quickinstall (nur nötig wenn python3 < 3.12):
#     curl https://pyenv.run | bash
#     # danach pyenv in die Shell einbinden (.bashrc/.profile neu laden, s. pyenv-Ausgabe)
#     exec "$SHELL"          # oder Terminal neu öffnen, damit pyenv im PATH ist
#     pyenv install 3.12
#     pyenv local 3.12       # legt eine .python-version im Projektordner an
#   Ab jetzt verweist 'python3' im Ordner auf 3.12 (kein Ersetzen der Aufrufe nötig).

# Virtuelle Umgebung + Abhängigkeiten:
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt   # eine Quelle fuer alle Envs -> Pi und Dev-Laptops identisch
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
-- Hinweis: IF NOT EXISTS legt den User NUR beim ersten Mal an. Existiert er
-- bereits, bleibt das alte Passwort aktiv. Bei Re-Setup oder Passwort-Rotation
-- stattdessen ALTER USER verwenden:
--   ALTER USER 'alarm'@'127.0.0.1' IDENTIFIED BY 'NEUES_PASSWORT';
EXIT;
```

> Das Passwort hier ist ein **Platzhalter** — echtes PW aus dem Passwort-Manager einsetzen, nicht committen.

---

## 4. Schema + Rechte einspielen (Reihenfolge zwingend: ERST Schema, DANN Grants)

```bash
# 4a) Tabellen anlegen (idempotent):
sudo mariadb alarmsystem < migrations/schema.sql

# 4b) Least-Privilege-Rechte (append-only, NF-09) vergeben.
#     grants.sql vergibt an einen festen Host-Specifier (aktuell 'alarm'@'localhost').
#     Unser App-User ist 'alarm'@'127.0.0.1' (PyMySQL verbindet per TCP). Wir schreiben
#     deshalb beim Einspielen NUR den Host des App-Users 'alarm' auf '127.0.0.1' um
#     -> egal ob grants.sql 'localhost', '%' o.ä. nutzt, die Rechte landen beim richtigen User.
#     Der enge Scope 'alarm'@ lässt etwaige weitere User/Host-Angaben unberührt (grants.sql
#     enthält aktuell nur 'alarm'). migrations/grants.sql im Repo bleibt UNVERÄNDERT.
#     --force: hier NUR, damit die harmlosen REVOKE-Hinweise auf frischem User das Einspielen nicht
#              abbrechen. WICHTIG: --force macht den Client bei JEDEM SQL-Fehler stumm weitermachen —
#              auch wenn ein GRANT komplett ausbleibt (sed trifft nicht, Tabelle fehlt, Syntaxfehler).
#              Deshalb ist der SHOW GRANTS-Pflichtcheck unten der einzig verlässliche Beweis, dass die
#              Rechte wirklich angekommen sind. Zeigt er nur 'USAGE', ist grants.sql trotz Exit 0
#              gescheitert -> Schritt 4b nochmal ohne --force laufen lassen, um die echte Fehlermeldung zu sehen.
sed "s/'alarm'@'[^']*'/'alarm'@'127.0.0.1'/g" migrations/grants.sql | sudo mariadb --force alarmsystem
```

> ⚠️ **Pflicht-Check direkt danach (nicht überspringen):** Die `SHOW GRANTS`-Verifikation unten beweist
> sofort, dass `alarm`@`127.0.0.1` die Rechte wirklich bekommen hat. Sie ist der Schutz davor, dass eine
> Host-Verschiebung in `grants.sql` unbemerkt bleibt und erst später unter Last als `ERROR 1142` auffällt.
> (Das `'alarm'@'[^']*'`-Muster oben fängt jede Host-Schreibweise des App-Users ab — der Check ist trotzdem Pflicht.)

**Verifikation (als Admin) — Pflicht, nicht optional:**
```bash
sudo mariadb -e "SHOW GRANTS FOR 'alarm'@'127.0.0.1';"
# Muss INSERT/SELECT (+ UPDATE auf Tabelle 'alarm') je Tabelle zeigen — KEIN 'ALL PRIVILEGES'.
#   Hinweis: 'alarm' ist hier der TABELLENNAME (die Alarm-Tabelle braucht UPDATE für State-Übergänge),
#   nicht der DB-User. DB-User und Tabelle heißen gleich — Verwechslungsgefahr.
# Zeigt es NUR 'USAGE' (= keine Tabellen-Rechte) -> grants.sql kam nicht beim User an -> Schritt 4b prüfen.
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
  Braucht **uvicorn ≥ 0.21** (in `requirements.txt` mit `>=0.30` abgedeckt). Ältere Installs kennen das
  Flag nicht → Start scheitert mit `Unknown argument`; dann uvicorn aktualisieren (`pip install -U -r requirements.txt`).
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

## 10. Frontend (G3-SPA) mitservieren — optional, Same-Origin

Das G3-Frontend (React/Vite) wird **vom selben G2-Backend** mit ausgeliefert: Der Browser holt die
Oberfläche von `http://<pi>:8000/`, die API liegt unter `/v1` (gleiche Origin → **kein CORS nötig**).
Steuert sich über die Env `G2_FRONTEND_DIR`; ist sie nicht gesetzt, läuft G2 wie bisher als reine API.

**a) Build (einmalig, auf einem Rechner mit Node ≥ 20 — schneller als auf dem Pi):**
```bash
cd <frontend-repo>/code
echo "VITE_API_MODE=live" > .env.production   # ⚠️ WICHTIG: ohne das zeigt die UI Mock-Daten!
npm ci
npm run build                                  # erzeugt code/dist/  (index.html + assets/)
```

**b) `dist/` auf den Pi kopieren** (nicht ins Git — Build-Artefakt):
```bash
rsync -av code/dist/ pi@icedetection.local:/home/pi/frontend_dist/
# oder: scp -r code/dist/* pi@icedetection.local:/home/pi/frontend_dist/
```

**c) In `.env` auf dem Pi den Pfad setzen + uvicorn neu starten:**
```
G2_FRONTEND_DIR=/home/pi/frontend_dist
```
```bash
curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/            # -> index.html [200]
curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/dashboard   # -> index.html [200] (SPA-Fallback)
curl -s -w "\n[%{http_code}]\n" http://127.0.0.1:8000/v1/health   # -> {"status":"ok"} [200] (API-Vorrang)
```

> Deep-Links (`/dashboard`, Reload) liefern `index.html` (React-Router übernimmt clientseitig);
> `/v1/*` bleibt **immer** die API (auch ein 404 dort ist ein API-404, kein HTML). Ohne gesetztes
> `G2_FRONTEND_DIR` ist der Mount ein No-op — die API verhält sich unverändert.

---

## Sicherheits-Regeln (kurz)

- **DB nur lokal** (`127.0.0.1`) — MariaDB nicht auf `0.0.0.0` öffnen. (NF-07)
- **API-Port (8000) im unsicheren Netz einschränken.** `--host 0.0.0.0` (Schritt 6) macht die API für **alle**
  Geräte im Netz sichtbar — gewollt für G3/Tests im vertrauenswürdigen LAN. Läuft der Pi in einem **offenen/
  fremden** Netz, den Port auf bekannte IPs begrenzen, z. B. nur G3 freigeben:
  ```bash
  sudo ufw allow ssh                                   # ZUERST! sonst kappt 'ufw enable' die laufende SSH-Sitzung
  sudo ufw allow from <G3-IP> to any port 8000 proto tcp
  sudo ufw enable
  ```
  (Alternativ den Pi nur über ein isoliertes/Test-LAN betreiben.) Die DB bleibt davon unberührt lokal (`127.0.0.1`).
- **Passwörter nie committen.** Echte Werte im Passwort-Manager / in `.env` (gitignored). Vorlage = `.env.example`.
- **`alarm`** darf nur `alarmsystem` und nur INSERT/SELECT(+UPDATE auf Tabelle `alarm`) — append-only (NF-09).
  *Achtung Namensgleichheit:* DB-User `alarm` und Tabelle `alarm` heißen identisch.
- G1/G3 reden mit der **API**, nie direkt mit der DB (RB-01).

## Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| `ERROR 1142` bei App-Queries | User-Host passt nicht zur Verbindung. App nutzt TCP → User muss `@'127.0.0.1'` (oder `@'%'`) sein, und grants.sql mit demselben Host einspielen (Schritt 4b). |
| `Access denied for user 'alarm'` | Falsches PW in `.env` oder User nicht angelegt (Schritt 3). |
| `assessment/current` immer `503` | DB leer (noch keine Bewertung). Erwartet ohne Scheduler/G1 — kein Fehler. |
| `/v1/health` vom Laptop nicht erreichbar | uvicorn mit `--host 0.0.0.0` gestartet? Pi-Firewall/Port 8000 offen? |
| `REVOKE … ERROR 1141/1064` beim Grants-Einspielen | Harmlos auf frischem User; `--force` überspringt (Schritt 4b). |
| App-Queries `ERROR 1142`, obwohl Grants-Einspielen „erfolgreich" | `--force` macht den Client bei **jedem** SQL-Fehler stumm — auch ein komplett ausgebliebener GRANT (sed trifft nicht, Tabelle fehlt) erzeugt keinen Abbruch. Einziger verlässlicher Beweis: `SHOW GRANTS` zeigt nur `USAGE` → Grants kamen nicht an → Schritt 4b **ohne** `--force` wiederholen, um die echte Fehlermeldung zu sehen. |

## Schnellreferenz

| Aktion | Befehl |
|---|---|
| Auf Pi verbinden | `ssh pi@icedetection.local` |
| DB-Konsole (Admin) | `sudo mariadb` |
| DB-Konsole (App) | `mariadb -h 127.0.0.1 -u alarm -p alarmsystem` |
| Schema einspielen | `sudo mariadb alarmsystem < migrations/schema.sql` |
| Rechte einspielen | `sed "s/'alarm'@'[^']*'/'alarm'@'127.0.0.1'/g" migrations/grants.sql \| sudo mariadb --force alarmsystem` |
| Rechte prüfen | `sudo mariadb -e "SHOW GRANTS FOR 'alarm'@'127.0.0.1';"` |
| DB-Backup (Dauerbetrieb) | `mysqldump alarmsystem > backup_$(date +%F).sql` |
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
#   "Change the root password?" -> N  (sonst bricht die unix_socket-Auth, 'sudo mariadb' geht nicht mehr)
```
Danach weiter bei **Schritt 3**.
