# Lokale DB einrichten & DB-Integrationstests laufen lassen

> **Stand 2026-06-27 (DB-Finalisierung).** Die DB-Integrationstests (`tests/test_*_integration.py`,
> `tests/test_storage_repository.py`, `tests/test_storage_database.py`) **skippen automatisch**, wenn keine
> MariaDB erreichbar ist. Damit sie laufen, braucht es eine erreichbare MariaDB/MySQL und die `DB_*`-Env.
> Ohne DB bleibt die Suite grün (die Tests werden übersprungen) — die echte Persistenz wird dann aber
> **nicht** geprüft. Genau das war bis 27.06. der Fall (siehe „Hintergrund" unten).

## Was die Tests brauchen

- Eine erreichbare **MariaDB ≥ 10.6 / MySQL 8** (Projekt-Default MariaDB, E-29).
- Einen DB-User, der **`CREATE DATABASE` + `TRUNCATE`** darf (die Test-Fixtures legen eine
  Wegwerf-DB `<DB_NAME>_test` an und räumen Tabellen) — **nicht** der Least-Privilege-App-User.
- Diese Umgebungsvariablen (siehe `.env.example`):
  `DB_HOST`, `DB_PORT` (3306), `DB_NAME` (z. B. `alarmsystem`), `DB_USER`, `DB_PASSWORD`.
  Optional: `DB_NAME_TEST` überschreibt den Namen der Wegwerf-Test-DB (Default `<DB_NAME>_test`).
  Optional: `DB_FORCE_RECREATE=1` droppt die Test-DB vor dem Lauf und baut sie frisch aus `schema.sql`
  auf — **nötig nach Schema-Änderungen** (neue Spalten/Enums). `CREATE DATABASE IF NOT EXISTS` greift
  bei bereits existierender Test-DB nicht auf Spaltenebene; ohne dieses Flag läuft die Suite sonst still
  gegen ein veraltetes Schema.

> ⚠️ **`.env`-Falle:** Der `.env.example`-Default `DB_USER=alarm` ist der Least-Privilege-App-User
> und darf **kein** `CREATE DATABASE`. Wer `.env.example` 1:1 nach `.env` kopiert und `pytest` ohne
> Override startet, bekommt einen harten **`CREATE DATABASE ... denied`-Fehler** (keinen sauberen
> Skip, weil `SELECT 1` als `alarm` noch durchgeht). Für die Tests `DB_USER=app` (GRANT ALL) setzen —
> wie in den Kommandos unten.

## Schnellstart A — portable MariaDB unter Windows (kein Admin, kein Installer)

Auf diesem Entwicklungsrechner verwendet — funktioniert ohne Admin-Rechte und ohne Dienst:

```powershell
# 1) ZIP von downloads.mariadb.org holen (winx64, z. B. 11.4.x LTS), entpacken nach
#    %LOCALAPPDATA%\alarm-mariadb\dist\mariadb-<ver>-winx64
# 2) Datenverzeichnis initialisieren
& "<bin>\mariadb-install-db.exe" --datadir="%LOCALAPPDATA%\alarm-mariadb\data"
# 3) init.sql (NICHT committen) anlegen: DB + Users als @'%' (siehe Gotcha unten)
#    CREATE DATABASE IF NOT EXISTS alarmsystem CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
#    CREATE USER IF NOT EXISTS 'app'@'%'   IDENTIFIED BY '<dev-pw>';  GRANT ALL ON *.* TO 'app'@'%' WITH GRANT OPTION;
#    CREATE USER IF NOT EXISTS 'alarm'@'%' IDENTIFIED BY '<dev-pw>';
# 4) Server starten (Loopback; Loopback ist firewallfrei)
& "<bin>\mariadbd.exe" --no-defaults --datadir="...\data" --basedir="...\mariadb-<ver>-winx64" `
    --port=3306 --bind-address=127.0.0.1 --init-file="...\init.sql"
```

## Schnellstart B — native MariaDB unter Linux/WSL

```bash
sudo apt-get install -y mariadb-server
sudo service mariadb start
sudo mariadb -e "CREATE DATABASE IF NOT EXISTS alarmsystem CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mariadb -e "CREATE USER IF NOT EXISTS 'app'@'%' IDENTIFIED BY '<dev-pw>'; GRANT ALL ON *.* TO 'app'@'%' WITH GRANT OPTION;"
sudo mariadb -e "CREATE USER IF NOT EXISTS 'alarm'@'%' IDENTIFIED BY '<dev-pw>';"
```

## Schema + Rechte einspielen

```bash
cd 04-Source-code   # relative Pfade migrations/*.sql gelten ab hier
# Schema (idempotent). Die Test-Fixtures laden es selbst in die _test-DB; fuer die "echte"
# alarmsystem-DB (App-Betrieb) einmalig manuell:
mariadb -h127.0.0.1 -P3306 -u app -p alarmsystem < migrations/schema.sql
# Least-Privilege-Rechte (NF-09 append-only) auf den App-User anwenden:
#   -> grants.sql nutzt 'alarm'@'localhost'. Bei TCP-Verbindungen (127.0.0.1) den Host-Specifier
#      auf 'alarm'@'%' anpassen, sonst ERROR 1142 (siehe Gotcha).
mariadb -h127.0.0.1 -P3306 -u app -p alarmsystem < migrations/grants.sql
```

## Integrationstests laufen lassen

```bash
cd 04-Source-code
DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=alarmsystem DB_USER=app DB_PASSWORD=<dev-pw> \
  python -m pytest -q
# Nur die DB-Integrationstests:
DB_HOST=127.0.0.1 ... python -m pytest tests/test_storage_repository.py \
  tests/test_alarm_repository_integration.py tests/test_assessment_repository_integration.py -v
```

Erwartung mit erreichbarer DB: alle 4 MySql-Repos (reading/alarm/assessment/audit) grün; volle Suite grün.

## Gotchas (real aufgetreten, nicht theoretisch)

- **`@'localhost'` vs. `@'%'`:** `grants.sql` vergibt an `'alarm'@'localhost'`. „localhost" matcht in MySQL nur
  Socket-/Named-Pipe-Verbindungen. Eine **TCP**-Verbindung (auch zu `127.0.0.1`, oder aus einem Container)
  erscheint serverseitig **nicht** als `localhost` → der User muss als `@'%'` (oder `@'127.0.0.1'`) angelegt
  und berechtigt werden, sonst `ERROR 1142 ... command denied`.
- **WSL2 + Docker:** Auf diesem Rechner publiziert die Docker-Engine Ports **nicht** ins erreichbare Netz
  (Container ohne Netz-Endpoint) — weder Windows noch der WSL-Host erreichen `3306`. Deshalb Docker hier
  **nicht** verwendet (siehe Hintergrund). Wer Docker nutzt: Erreichbarkeit von der Test-Umgebung aus zuerst
  separat prüfen.
- **`mariadb.exe`-CLI unter Windows/PowerShell:** `-h127.0.0.1` wird teils zu Host `'127'` zerlegt
  (DNS-Fehler). `pymysql` (die Tests) ist davon nicht betroffen; fürs CLI `--host=127.0.0.1 --protocol=tcp`
  verwenden.

## Hintergrund (warum so)

Die DB-Infrastruktur-Tickets DTB-53/54/55/56 standen auf Jira „Erledigt", aber eine **reale MariaDB war nie
hochgezogen** (Hardware-Problem im ursprünglichen Setup). Folge: der einzige Real-DB-Integrationstest
(DTB-27 T4) hat immer nur ge-skippt — **kein SQL lief je gegen eine echte DB**. Bei der Finalisierung am
27.06. wurde zuerst ein schlummernder Bug im Schema-Lader gefunden (naives `ddl.split(';')` zerschnitt einen
Kommentar mit `;` → SQL-1064; gefixt via `tests/_sql_splitter.py`). Anschließend wurden alle vier MySql-Repos
und die NF-09-Append-only-Rechte gegen eine echte MariaDB verifiziert.

> **Konform zu DTB-53 / E-35 („kein Docker", native MariaDB).** Genutzt wird **Option (b)** aus DTB-53 —
> lokale native MariaDB auf Windows — als **portables ZIP** statt winget (vermeidet den UAC-Installer-Prompt),
> funktional identisch. Ein anfänglicher Docker-Versuch wurde verworfen (Engine auf dem Rechner defekt) —
> Docker war ohnehin per E-35 ausgeschlossen, also **keine** Abweichung. Für den dauerhaften Team-/Demo-Betrieb
> bleibt die DB-Bereitstellung (geteilte Pi vs. lokal je Entwickler) eine offene Frage (→ M3, DTB-17/23).
