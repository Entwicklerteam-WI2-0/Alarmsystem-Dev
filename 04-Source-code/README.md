# G2-Backend — Vereisungserkennung ANR

Backend-Repo der Gruppe 2 (FastAPI · MySQL/MariaDB · rohes PyMySQL, kein ORM). Struktur nach
`../02-Arbeitsdokumente/Backend-Konzept.md` §7, Tasks nach `../02-Arbeitsdokumente/Tasks+Projektplan.md`.

## Struktur
- `src/ingest/` — Poller gegen G1 (`GET /current`, `GET /health`), Eingangsvalidierung
- `src/model/` — Pydantic-Schemas + Enums (6 Entitäten: reading/assessment/alarm/acknowledgement/threshold_set/audit_log); DB-DDL in `migrations/schema.sql`
- `src/assessment/` — Vereisungslogik (4-Stufen) — Kernmodul, hohe Testabdeckung
- `src/alarm/` — Alarm-Generierung (Severity aus RiskLevel, Hysterese/Entprellung); Persistenz in `storage/`
- `src/storage/` — DB-Zugriff (Repository-Pattern, rohes PyMySQL → MySQL/MariaDB; kein ORM, E-35)
- `src/api/` — Serving-Endpoints für G3
- `src/config/` — Schwellen/Parameter (parametrierbar)
- `src/forecast/` — 30-min-Prognose (T3)
- `migrations/` — `schema.sql` (handgeschriebenes DDL; kein Alembic, E-35) + `grants.sql` (App-User-Rechte, append-only NF-09)
- `tests/` — Unit-/Integrationstests
- `config/` — Default-Schwellenwerte (Dummy, parametrierbar)

## Setup (lokal, Windows)
    cd 04-Source-code
    py -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements-dev.txt
    # MariaDB: native — Pi via SSH-Tunnel ODER lokale Installation (kein Docker, E-35)
    # Zugangsdaten über .env (s. .env.example), nie committen
    # Schreibzugriff (POST /v1/thresholds, DTB-63/NF-07): G2_API_KEY in .env setzen;
    # ungesetzt -> Schreib-Endpoints antworten fail-safe mit 503. TLS am Reverse-Proxy.
    uvicorn src.main:app --reload    # -> http://127.0.0.1:8000

## Schema & DB-Rechte einspielen (DDL, ersetzt Alembic — E-35)

Kein Migrationsframework. Das Schema wird direkt eingespielt; `schema.sql` ist idempotent
(`CREATE TABLE IF NOT EXISTS`) — ein **Erst-Apply** ist gefahrlos wiederholbar. **Achtung:** bei
*geänderter* Tabellenstruktur migriert `IF NOT EXISTS` **nicht** (Drift) → Strukturänderung = manuell
DROP/ALTER.

**DB-Kompatibilität:** `schema.sql` läuft auf **MariaDB** (Projekt-Default, E-29) **und MySQL 5.7/8.0**.
`CREATE TABLE IF NOT EXISTS` ist beidem gemein. Für bedingte `ALTER TABLE`-Migrationen (z. B. nachträglich
hinzugefügte Spalten/Indizes) wird statt der MariaDB-spezifischen Syntax `ADD/DROP ... IF [NOT] EXISTS`
über `INFORMATION_SCHEMA` geprüft und nur bei Bedarf `ALTER TABLE` via `PREPARE`/`EXECUTE` ausgeführt.
Das vermeidet Syntaxfehler auf älteren MySQL-Versionen (< 8.0.21), die Flughafen-Betriebsumgebungen noch
verwenden können.

**Zwei Rollen** (nicht verwechseln): den **Admin-User `root`** (`DB_ROOT_PASSWORD`) zum Einspielen von
DDL + Rechten; den **App-User `alarm`** (`DB_USER`) nutzt nur die App. Voraussetzung: laufende MariaDB
oder MySQL, App-User existiert (DB-Init), Zugangsdaten in `.env` (s. `.env.example`), nie committen.

> Pi via SSH-Tunnel: zuerst `ssh -L 3306:localhost:3306 <pi>` öffnen, dann gegen `127.0.0.1` einspielen.
> `docker-compose.yml` ist **abgewählt** (E-35: native MariaDB, kein Docker) und **bereits entfernt** — **nicht**
> `docker compose up` als Setup-Pfad nutzen.

Einspielen **als `root`**, Reihenfolge `schema.sql` → `grants.sql` (cwd = `04-Source-code`):

    # PowerShell (Windows-Standardshell — '<' funktioniert hier NICHT).
    # Bei Erstinstallation liefert grants.sql ERROR 1141 (keine bestehenden Grants);
    # der mysql-Client setzt fort, gibt aber Exit-Code != 0 zurueck. Daher
    # $ErrorActionPreference = 'Stop' hier vermeiden oder Exit-Code ignorieren.
    Get-Content migrations\schema.sql | mysql -h 127.0.0.1 -P 3306 -u root -p alarmsystem
    Get-Content migrations\grants.sql | mysql -h 127.0.0.1 -P 3306 -u root -p alarmsystem

    # cmd.exe / Linux-Shell (Eingabe-Umleitung '<' ok).
    # Auch hier kann grants.sql bei Erstinstallation Exit-Code != 0 liefern.
    mysql -h 127.0.0.1 -P 3306 -u root -p alarmsystem < migrations/schema.sql
    mysql -h 127.0.0.1 -P 3306 -u root -p alarmsystem < migrations/grants.sql

> **Maßgeblich ist die Verifikation via `SHOW GRANTS FOR 'alarm'@'localhost';`**, nicht der Exit-Code.

**Verifikation** (läuft bei der MariaDB-Initialisierung am Pi — DTB-54 DoD-Nachweis, noch offen):

    # 1) alle 6 Tabellen vorhanden:
    mysql -u root -p -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='alarmsystem';" 
    # erwartet: 6  (reading, assessment, alarm, acknowledgement, threshold_set, audit_log)

    # 2) Typen/Charset/Indizes stichprobenhaft (-E = vertikale Ausgabe; \G wirkt bei -e NICHT):
    mysql -u root -p alarmsystem -E -e "SHOW CREATE TABLE reading;"
    mysql -u root -p alarmsystem -e "SHOW INDEX FROM reading;"

    # 3) Idempotenz: schema.sql ein zweites Mal einspielen -> muss fehlerfrei durchlaufen.

    # 4) append-only (NF-09) erzwungen? Rechte des App-Users prüfen + Negativ-Test:
    mysql -u root  -p -e "SHOW GRANTS FOR 'alarm'@'localhost';"
    mysql -u alarm -p alarmsystem -e "UPDATE audit_log SET actor='x' WHERE id=1;"
    mysql -u alarm -p alarmsystem -e "UPDATE reading SET air_temp_c=0 WHERE id=1;"
    # erwartet je: ERROR 1142 (UPDATE denied) — audit_log/acknowledgement UND
    # reading/assessment sind unveränderbar.

> **DTB-54 DoD — noch offen (vor dem Merge bei Pi-MariaDB-Init nachzuholen):**
> - [ ] (1) alle 6 Tabellen vorhanden (`COUNT(*) = 6`)
> - [ ] (2) Typen/Charset/Indizes stichprobenhaft geprüft
> - [ ] (3) Idempotenz: `schema.sql` 2× fehlerfrei eingespielt
> - [ ] (4) append-only erzwungen (Negativ-Test `ERROR 1142` für audit_log **und** reading)
>
> Prozess: diese Checkliste muss bei Pi-MariaDB-Init abgehakt und in Jira/DTB-54
> als Abschlussnachweis dokumentiert werden — nicht nur in dieser README.

## Tests
    pytest                 # alle Tests
    pytest --cov=src       # mit Coverage (Ziel: Bewertungslogik >= 80 %)

## Endpoints (G2, Stand 28.06.)
- `GET /v1/health` -> `{"status": "ok"}` (P0.3).
- `GET /v1/assessment/current` -> `AssessmentCurrent` (DTB-43). Fail-safe NF-01: Stale/Fault -> 200 `risk_level=unknown` (nie GRÜN); keine Bewertung/DB-Ausfall -> 503 `Error {code, message}`.
- `GET /v1/thresholds` -> `Thresholds` (DTB-62, NF-05): aktuell aktive Vereisungs-Schwellen (rein lesend, RB-01-neutral).
- `GET /v1/readings` -> `Reading[]` (DTB-34, FA-03): Messwert-Historie (T1). Query `from`/`to` (ISO-8601 UTC, inklusiv auf `measured_at`), `sensor_id`, `limit` (1..1000, Default 100), `order` (`asc`|`desc`, Default `desc`). Bei mehr Treffern als `limit` wird am älteren Ende abgeschnitten (frischeste `limit` bleiben). `from` nach `to` / `limit` außerhalb [1,1000] / ungültiges `order` -> 400 `Error {code, message}`; DB-Ausfall -> 503 `Error {code, message}`; `Cache-Control: no-store`.

## RB-01-Nachweis: erlaubte API-Endpoints

P4.5 / DTB-42 prueft RB-01 maschinell und im Review: Das Backend bleibt reine
Entscheidungsunterstuetzung. Es gibt keinen Endpoint, der die Startbahn freigibt,
sperrt, entsperrt oder ausfuehrt/steuert.

| Endpoint | Methode | RB-01-Begruendung |
|---|---:|---|
| `/v1/health` | GET | Readiness/Liveness, kein fachlicher Zustand der Startbahn. |
| `/v1/assessment/current` | GET | Liefert Bewertung/Status fuer Menschen; keine Steuerwirkung. |
| `/v1/thresholds` | GET | Liest Bewertungsparameter; rein informativ. |
| `/v1/thresholds` | POST | Legt versionierte Schwellenparameter mit Auth + Audit an; aendert nur die Bewertungslogik, keinen Runway-Status. |
| `/v1/readings` | GET | Liest Messwert-Historie; keine Steuerwirkung. |
| `/v1/alarms` | GET | Zustands-/Resync-Lesepfad fuer Alarme; kein Aktor. |
| `/v1/alarms/stream` | GET | SSE-Push fuer Alarme; sendet nur Ereignisse an G3. |
| `/v1/alarms/{id}/ack` | POST | Manuelle Quittierung/Audit eines Alarms; keine Freigabe/Sperrung der Bahn. |

Enforcement: `python tools/check_rb01_no_actor_endpoints.py` scannt FastAPI-Routen
und `docs/api/v1/openapi.yaml` auf `unlock`, `freigabe`, `sperr`, `execute`.
Der Check laeuft in `.pre-commit-config.yaml` und in `.github/workflows/lint-config.yml`.

## Datenfluss
`G1 (Sensorik)` ──poll `GET /current`──▶ `Ingest/Validierung` ──▶ DB `reading` ──▶ `Bewertung` (4-Stufen)
──▶ `assessment` (+ ggf. `alarm`) ──▶ DB ──▶ `API` ──GET (Alarme: SSE-Push)──▶ `G3 (Frontend)`.
**Fail-safe (NF-01):** bei Stale/Ausfall nie GRÜN → `unknown` + Warnung.

## Schnittstelle G1 → G2 (Contract, eingehend)

G1 liefert eine eigene Sensor-API; G2 pollt sie. Verbindlich:

```
GET /current → {
  "measured_at": "2026-06-22T14:03:05Z",   // PFLICHT — ein Zeitstempel für alle Werte
  "sensor_id": "anr-rwy-01",
  "surface_temp_c": -0.4,   // Pflicht-Trias für die Bewertung
  "air_temp_c": 1.2,        //
  "humidity_pct": 96,       //
  "pressure_hpa": 1013,     // optional/Kontext
  "status": "ok"
}

GET /health → 200 (ok) / 503 (fault)
```

`measured_at` und `/health` sind nicht verhandelbar; Feldnamen/Einheiten sonst Team-Sync.

## Schnittstelle G2 → G3 (Serving, ausgehend)

G2 ist **Server**; G3 konsumiert per `GET` (REST). Alle Endpoints unter `/v1/` (AE-03). Spec: DTB-19 / OpenAPI v1.
- `GET /v1/assessment/current` — aktuelle Risikostufe (`green|yellow|orange|red|unknown`) + Faktoren + Zeitstempel
- **Alarme = Push (E-37):** `GET /v1/alarms/stream` (SSE — G2 pusht Alarme live) + `GET /v1/alarms` (Zustands-Abfrage/Resync, **kein** Poll-Scan)
- `POST /v1/alarms/{id}/ack` (Quittierung — reine UI-/Audit-Aktion, **kein** Bahn-Aktor, RB-01)
- `GET /v1/readings` — Messwert-Historie (T1, DTB-34/FA-03): `from`/`to`/`sensor_id`/`limit`/`order`; **umgesetzt**
- `GET /v1/thresholds` — aktuelle Schwellenwerte lesen (DTB-62)
- `POST /v1/thresholds` — Schwellenwerte versioniert ändern (**Auth: `Authorization: Bearer <G2_API_KEY>`**, DTB-63); greift beim nächsten Reload (kein Live-Swap), versioniert per `threshold_set` + Audit (NF-09)

**Kein** Freigabe-/Sperr-Endpoint (RB-01). Stale/Ausfall → `unknown`, nie GRÜN (NF-01).

## G1-Sensor-Simulator (Dev-Test, ohne Sensor-Hardware)

Für live-nahe Tests der G1-Naht: **`tools/g1_sim/`** — steuerbarer Dummy-G1, bedient `GET /current` + `/health`
(konsumierter G1-Contract). Szenario per State-Datei **live umschaltbar** (grün/rot/stale/fault/down):

```bash
python tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json
# G2 dagegen (eigene Shell, gegen lokale MariaDB):
G1_BASE_URL=http://127.0.0.1:9101 G2_ENABLE_SCHEDULER=true uvicorn src.main:app --port 8000
```

Details + Szenario-/Erwartungs-Tabelle: **`tools/g1_sim/README.md`**. Lokale DB einrichten: **`docs/dev-db-setup.md`**.
Kein Produktiv-Bezug (liegt unter `tools/`, nicht von `src/` importiert).
