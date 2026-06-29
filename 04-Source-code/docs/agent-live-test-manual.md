# Agent Live-Test Manual — G2-Backend vollständig verifizieren

> **Zielgruppe:** KI-Coding-Agenten (Claude Code, Kimi Code, Codex CLI) und Menschen.
> Dieser Anleitung folgen, um das **komplette** Backend verlässlich zu testen — Unit, DB-Integration und Live-E2E.
>
> **Warum das existiert:** Bis 2026-06-28 skippten in vielen Session-Umgebungen 36 DB-Tests still, weil die
> `.env` nicht geladen wurde. Das ist inzwischen gefixt (pytest-dotenv, s. §1). Dieses Manual stellt sicher,
> dass jede Instanz denselben verifizierten Stand erreicht wie der Architekt — ohne Rätselraten.
>
> **Plattform-Hinweis:** Die Befehle sind primär auf **Windows** (Entwicklerrechner) formuliert — venv-Python
> liegt dann unter `.venv/Scripts/python.exe`. Auf **Linux/Mac/CI** liegt es unter `.venv/bin/python`;
> PowerShell-Cmdlets (`Get-NetTCPConnection`) und `tasklist` gibt es dort nicht ( stattdessen `ss -ltnp` /
> `ps aux | grep`). Die Plattform-Map steht in §6 (Troubleshooting). Alle Python-/pytest-/curl-Befehle
> selbst sind plattformunabhängig.

---

## 0. Voraussetzungen (einmalig, pro Rechner)

1. **Python 3.12+** (getestet bis 3.14).
2. **lokale MariaDB** auf `127.0.0.1:3306` — nativ, **kein Docker** (E-35). Setup: [`dev-db-setup.md`](dev-db-setup.md).
   Schnellstart A (Windows, portables ZIP, kein Admin) ist der empfohlene Pfad. Beim Anlegen der User auf
   `'app'@'%'` und `'alarm'@'%'` achten (TCP, nicht nur `localhost`).
3. **venv + deps** (aus `04-Source-code/`):
   ```bash
   py -m venv .venv
   ./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
   ```
4. **`.env`** im `04-Source-code/`-Verzeichnis (NICHT committen, NF-07). Aus `.env.example` ableiten, dann
   **zwingend** anpassen: echte DB-Creds + Live-Test-Defaults. Minimal:
   ```
   DB_HOST=127.0.0.1
   DB_PORT=3306
   DB_NAME=alarmsystem
   DB_USER=alarm
   DB_PASSWORD=<dein-dev-pw>
   G1_BASE_URL=http://127.0.0.1:9101
   G2_ENABLE_SCHEDULER=true
   G2_API_KEY=<lokaler-dev-key>
   ```
   Für die **Tests** muss `DB_USER=app` sein (hat `CREATE DATABASE`-Recht, braucht die Test-Fixture für die
   Wegwerf-DB `<DB_NAME>_test`) — entweder in der `.env` oder beim pytest-Aufruf überschreiben.

> **Agenten-Hinweis (wichtig):** Die `.env` ist ein Secret-File und wird vom Datei-Tool blockiert. Agenten
> können sie nicht mit `Read`/`Write` anlegen. Drei Wege:
> - User bittet, sie per Hand anzulegen (sauberster Pfad), **oder**
> - per Bash: `cp .env.example .env && sed -i 's/changeme/<echtes-pw>/' .env` (Linux/Git-Bash), **oder**
> - die Env-Variablen direkt im pytest-/uvicorn-Aufruf setzen (s. §2/§4) — dann braucht es keine `.env`.

---

## 1. Test-Ebene A — Unit + DB-Integration (automatisiert, mit pytest)

### Der footgun-Fix (Stand 2026-06-28)

**Früher:** `pytest` ohne `set -a && . ./.env` skippte 36 DB-Tests still (Default `DB_PASSWORD=changeme`
passte nicht zur echten DB → `db_available`-Fixture = False → skip).
**Jetzt:** `pytest-dotenv` (in `requirements-dev.txt`) lädt `.env` automatisch. Nacktes `pytest` reicht.

```bash
cd 04-Source-code
./.venv/Scripts/python.exe -m pytest -q
```
**Erwartet:** `851 passed, 0 skipped` (wenn MariaDB läuft + `.env` korrekt).
**Ohne DB:** `815 passed, 36 skipped` — die 36 Skips sind dann beabsichtigt (Fail-soft, kein Crash).

### CI-Sicherheit (`override=False`)

Konfiguriert in `pyproject.toml` (`env_override = false`): eine bereits gesetzte Prozess-Env gewinnt
gegen `.env`. In CI (ohne `.env`, mit Secrets als Prozess-Env) läuft die Suite weiter; lokale `.env`
überschreibt niemals CI-Secrets. Idempotent und sicher.

### Mit Coverage

```bash
./.venv/Scripts/python.exe -m pytest -q --cov=src
```
**Erwartet:** ~98 % Gesamt; `src/assessment`, `src/alarm`, `src/api` je 100 %.

### Nur DB-Integrationstests (die früher skippten)

```bash
./.venv/Scripts/python.exe -m pytest -q -k "integration or storage"
```
**Erwartet:** ~115 passed (alle 4 MySql-Repos: reading/alarm/assessment/audit + threshold_set + ack).

### Nach Schema-Änderungen (neue Spalten/Enums)

```bash
DB_FORCE_RECREATE=1 ./.venv/Scripts/python.exe -m pytest -q -k integration
```
`DB_FORCE_RECREATE=1` droppt die Test-DB und baut sie frisch aus `schema.sql` (sonst läuft die Suite still
gegen ein veraltetes Schema).

---

## 2. Test-Ebene B — Contract-Drift-Check (automatisiert)

Die eingefrorene API-Naht ist verbindlich. Guard-Tests prüfen Konsistenz Code ↔ Contract:

```bash
./.venv/Scripts/python.exe -m pytest tests/test_contract_enum_sync.py -v
```
**Erwartet:** grün. Bricht bei jeder Drift zwischen `src/model/enums.py`, `docs/api/v1/openapi.yaml` und
`docs/api/v1/g1-consumed.openapi.yaml`.

Zusätzlich die zwei Guard-Tools:
```bash
./.venv/Scripts/python.exe tools/check_hardcoded_thresholds.py     # keine hardcodierten Schwellen
./.venv/Scripts/python.exe tools/check_rb01_no_actor_endpoints.py  # kein Aktor-Endpoint (RB-01)
```

---

## 3. Test-Ebene C — Live E2E (G1-Sim → Backend → DB → API → Alarm)

Dafür braucht es eine **laufende** MariaDB + G1-Simulator + Backend. Drei Komponenten, drei Terminals.
Das vollständige, kommentierte Runbook steht in [`live-test-runbook.md`](live-test-runbook.md) — hier die
Kompaktversion für Agenten.

### 3a) MariaDB starten

```bash
# Windows, portables ZIP (dev-db-setup.md Schnellstart A):
"$LOCALAPPDATA/alarm-mariadb/dist/mariadb-<ver>-winx64/bin/mariadbd.exe" \
  --no-defaults --datadir="$LOCALAPPDATA/alarm-mariadb/data" \
  --basedir="$LOCALAPPDATA/alarm-mariadb/dist/mariadb-<ver>-winx64" \
  --port=3306 --bind-address=127.0.0.1 \
  --init-file="$LOCALAPPDATA/alarm-mariadb/init.sql"
```
**Check:** Port 3306 lauscht. Wenn schon ein MariaDB-Prozess läuft (s. §6), nicht nochmal starten.

### 3b) G1-Simulator starten (Fake-Sensor)

Eigene Shell, Hintergrund:
```bash
cd 04-Source-code
./.venv/Scripts/python.exe tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json
```
State-Datei vorab anlegen (falls nicht da): `cp tools/g1_sim/g1_state.example.json tools/g1_sim/g1_state.json`
und mit einem Start-Szenario befüllen (z. B. Grün: `surface_temp_c:15, air_temp_c:16, humidity_pct:40`).
**Check:** `curl http://127.0.0.1:9101/current` liefert einen Snapshot.

### 3c) Backend starten

Eigene Shell. Entweder `.env` ist korrekt gesetzt (dann einfach), oder Env inline:
```bash
cd 04-Source-code
DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=alarmsystem DB_USER=alarm DB_PASSWORD=<pw> \
G1_BASE_URL=http://127.0.0.1:9101 G2_ENABLE_SCHEDULER=true G2_API_KEY=<key> \
  ./.venv/Scripts/python.exe -m uvicorn src.main:app --port 8000 --log-level warning
```
> **`G2_ENABLE_SCHEDULER=true` ist Pflicht** — sonst pollt das Backend den Sim nicht und die Endpoints
> bleiben bei `503`. Klassische Falle, wenn jemand `.env.example` 1:1 übernimmt (dort steht `false`).

### 3d) Szenarien prüfen (via curl)

Warten bis zum ersten Poll (≤ 30 s), dann:
```bash
curl -s http://127.0.0.1:8000/v1/health             # {"status":"ok"}
curl -s http://127.0.0.1:8000/v1/assessment/current  # risk_level + Messwerte
```

Szenario umschalten: `tools/g1_sim/g1_state.json` editieren (Sim liest bei jedem Request neu).
**Sprung-Guard beachten** (s. live-test-runbook.md §3): Wechsel mit > 5 °C/min Sprung werden verworfen.
Für saubere Wechsel DB leeren + Backend neu starten (s. §5).

| Szenario | State-Values | Erwartete Ampel |
|---|---|---|
| GRÜN | `surface_temp_c:15, air_temp_c:16, humidity_pct:40` | `green` |
| ROT | `surface_temp_c:-2, air_temp_c:-1, humidity_pct:98` | `red` + CRITICAL-Alarm (nach 60 s) |
| STALE | `age_s:300` | `unknown` (nie grün, NF-01) |
| FAULT | `status:"fault"` | `unknown` (nie grün, NF-01) |
| G1-DOWN | `health_down:true` | `unknown` (nie grün, NF-01) |

### 3e) Alarm-Subsystem prüfen

```bash
curl -s "http://127.0.0.1:8000/v1/alarms?limit=5"            # Zustand/Resync
curl -N http://127.0.0.1:8000/v1/alarms/stream               # SSE-Live-Stream (abbrechen mit Ctrl-C)
curl -s -X POST http://127.0.0.1:8000/v1/alarms/1/ack \
  -H "Content-Type: application/json" -d '{"operator":"Test","note":"live"}'  # Quittierung (200)
curl -s -X POST http://127.0.0.1:8000/v1/alarms/1/ack \
  -H "Content-Type: application/json" -d '{"operator":"Test"}'                # Double-Ack -> 409
```

### 3f) Audit-Log in der DB prüfen

```bash
./.venv/Scripts/python.exe -c "
import pymysql
c=pymysql.connect(host='127.0.0.1',port=3306,user='app',password='<pw>',database='alarmsystem',autocommit=True)
with c.cursor(pymysql.cursors.DictCursor) as cur:
    cur.execute('SELECT event_type, COUNT(*) AS n FROM audit_log GROUP BY event_type ORDER BY n DESC')
    for r in cur.fetchall(): print(r)
    cur.execute('SELECT id,ts,event_type,entity_type,entity_id,actor,detail FROM audit_log ORDER BY id DESC LIMIT 10')
    for r in cur.fetchall(): print(r)
c.close()
"
```
**Erwartet:** `assessment_made`-Einträge pro Bewertung, `alarm_raised` bei ROT, `alarm_acknowledged` nach ack.

---

## 4. Die dokumentierten Vorfälle verifizieren (DoD §8)

Diese zwei Szenarien sind der Kern der Sicherheit und der Note (40 % Reflexion). Sie sind als **benannte
Tests** verankert, sodass man sie in Sekunden prüfen kann:

```bash
./.venv/Scripts/python.exe -m pytest tests/test_assessment.py -v -k vorfall
./.venv/Scripts/python.exe -m pytest tests/test_assessment_service_integration.py -v -k vorfall
```
**Erwartet:** 4 grün (2 Unit-Level `test_vorfall_1/2_*` + 2 Integration-Level mit Persistenz + ΔT-in-Explanation).

- **Vorfall 1** (Fehlalarm vermieden): Luft −2,1 °C, Oberfläche trocken (ΔT=7,9 K) → `YELLOW`, **kein** ROT.
- **Vorfall 2** (Eis erkannt): Luft +1,2 °C, Oberfläche gefroren + Reif (ΔT=−0,5 K) → `RED` + ΔT in Explanation.

> **Das ΔT-in-Explanation-Assertion** ist der Beweis, dass das Feature „Taupunktabstand verhindert
> Fehlalarme" nicht nur rechnet, sondern im operatorlesbaren Text sichtbar wird.

---

## 5. Sauberen Szenariowechsel vorbereiten (Live)

Bei Sprüngen > 5 °C/min verwirft der Poller das Reading (Sensordefekt-Verdacht). Für einen sauberen
Ampelwechsel in §3: DB leeren + Backend neu starten, Ziel-State **vor** erstem Poll setzen.

```bash
# DB leeren (privilegierter User `app`):
./.venv/Scripts/python.exe -c "
import pymysql
c=pymysql.connect(host='127.0.0.1',port=3306,user='app',password='<pw>',database='alarmsystem',autocommit=True)
with c.cursor() as cur:
    # FK-Safe: Checks vor TRUNCATE deaktiviert, danach wiederhergestellt. Sonst kann InnoDB
    # bei assessment.reading_id (FK auf reading) oder alarm.assessment_id den TRUNCATE verweigern.
    cur.execute('SET FOREIGN_KEY_CHECKS=0')
    for t in ('alarm','assessment','reading','acknowledgement','audit_log'):
        cur.execute(f'TRUNCATE {t}')
    cur.execute('SET FOREIGN_KEY_CHECKS=1')
c.close()
"
# dann Backend neu starten.
```

> **`audit_log` mit leeren** — sonst bleiben nach einem Live-Lauf `alarm_raised`/`alarm_acknowledged`-
> Einträge stehen und die Audit-Prüfung in §3f zeigt veraltete Altdaten. `audit_log` ist im Betrieb
> append-only (NF-09); `TRUNCATE` als privilegierter User nur für lokale Tests, nie in Produktion.

---

## 6. Troubleshooting (die echten Fallen)

| Symptom | Ursache | Fix |
|---|---|---|
| 36 Tests skippen | `.env` fehlt/falsch, DB_PASSWORD-Default `changeme` greift | `.env` anlegen mit echtem PW (§0); ab Fix läuft alles auto. |
| 36 Tests skippen **trotz** `.env` | pytest wird **nicht aus `04-Source-code/`** aufgerufen — `env_files=[".env"]` wird relativ zum CWD aufgelöst, nicht zur `pyproject.toml` | `cd 04-Source-code` vor pytest; `.env` muss im CWD liegen |
| `/v1/assessment/current` = `503` | Scheduler aus (`G2_ENABLE_SCHEDULER=false`) ODER DB-Verbindung fehlgeschlagen | `G2_ENABLE_SCHEDULER=true` setzen; Server-Log prüfen (`Umgebungsvariable fehlt...`) |
| Ampel ändert sich nicht bei Szenariowechsel | Sprung-Guard hat Reading verworfen | DB leeren + Backend neu starten (§5) |
| `ERROR 1142 ... command denied` | `'alarm'@'localhost'` statt `'alarm'@'%'` (TCP vs. Socket) | User als `@'%'` anlegen (dev-db-setup.md) |
| Rot/Orange, obwohl trocken | Taupunkt falsch berechnet? Magnus-Pol (`air_temp <= -b`) | `air_temp_c` muss > Magnus-Grenze sein; sonst `dew_point_c=None` → Fail-safe |
| `mariadb.exe -h127.0.0.1` zerfällt zu Host `'127'` | Windows-CLI-Bug | `--host=127.0.0.1 --protocol=tcp` nutzen; pymysql ist nicht betroffen |
| MariaDB schon am Laufen? | Vor Start prüfen, nicht doppelt starten | Windows: `tasklist \| grep mariadbd`; Linux: `ss -ltnp \| grep 3306` |
| `.venv/Scripts/python.exe` nicht gefunden | Linux/Mac — dort liegt venv-Python woanders | Linux/Mac: `.venv/bin/python` nutzen (großes Theme dieses Manuals) |
| PowerShell-Cmdlet nicht verfügbar (`Get-NetTCPConnection`) | Linux/Mac hat keine PowerShell-Cmdlets | Linux: `ss -ltnp \| grep :8000`; Mac: `lsof -i :8000` |

---

## 7. Cleanup nach dem Test

```bash
# Prozesse stoppen (Ports 8000, 9101) — Backend-/Sim-Fenster schließen oder:
# Windows:
# (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess | %{ Stop-Process -Id $_ -Force }
# MariaDB läuft weiter (kein Dienst, nur Prozess) — kann für nächste Session bleiben.
```
MariaDB nicht killen, wenn andere Sessions sie noch nutzen.

---

## 8. Vom Sim zum echten G1 (Vor-Ort / Pi-Deploy)

§1–§7 testen gegen den **G1-Sim** (Fake-Sensor). Für die **Vor-Ort-Integration** (echter G1 von Nils,
G3-Frontend von Nick) wird der Sim **nicht** gestartet — das Backend pollt jede `GET /current`-Quelle
gleich, es ändern sich nur die Env-Werte. Der Ablauf ist über den **STOA-Real-Test (28.06.)** erprobt.

**Erprobte Start-Reihenfolge:** native MariaDB → `schema.sql` → `grants.sql` → `.env` → `uvicorn`.
DB-Setup-Details: [`dev-db-setup.md`](dev-db-setup.md) (Source of Truth). Hier nur die G1/G3-spezifischen
Env-Umstellungen **gegenüber dem lokalen Sim-Test** (§0):

| Env | Sim-Test (§0) | Vor-Ort / echter G1 |
|---|---|---|
| `G1_BASE_URL` | `http://127.0.0.1:9101` (Sim) | echter G1-Endpoint (Adresse per Seam-Sync; Code-Default `http://g1-sensorik.local`) |
| `G2_CORS_ORIGINS` | ungesetzt → `*` | **Origin des G3-Frontends** setzen, z. B. `http://devpi.local:3000` — statt Wildcard |
| `G2_API_KEY` | lokaler Dev-Key | echter Key. **Ohne** gesetzten Key lehnt G2 jeden Schreibzugriff mit `503` ab (fail-safe-closed) |
| `G2_ENABLE_SCHEDULER` | `true` | `true` (Scheduler scharf — wie beim Sim) |

> ⚠️ **Pre-Prod-HTTP-Gate:** Der Default `G1_BASE_URL=http://g1-sensorik.local` ist bewusst **HTTP** (G1 ist
> HTTP-only, eingefrorene Naht). Für die Vor-Ort-Integration bleibt HTTP ok; **vor echtem Produktivbetrieb**
> auf HTTPS umstellen — **per Env** (`G1_BASE_URL=https://g1-sensorik.local`), **nicht** im Code hart
> erzwingen (würde den HTTP-only-G1 brechen). Quelle: `src/main.py` (`_DEFAULT_G1_BASE_URL`).

> **Kein Sprung-Guard-Reset vor Ort:** Die DB-Leer-Prozedur aus §5 ist ein reines **Sim-Artefakt**
> (künstliche Szenariosprünge > 5 °C/min). Echte Sensorwerte ändern sich langsam → der Sprung-Guard greift
> im Normalbetrieb nicht; **nicht** „aus Gewohnheit" die DB leeren — im Betrieb sind `reading`/`assessment`
> append-only (NF-09).

**Verifikation vor Ort** = §3d–§3f gegen den echten G1 (statt Sim): `/v1/health` = ok,
`/v1/assessment/current` liefert die zur realen Messlage passende Ampel, Alarm-Subsystem + Audit-Log schreiben.

---

## Kurz-Checkliste für Agenten (vor „V1 funktioniert"-Behauptung)

- [ ] `pytest -q` → `851 passed, 0 skipped` (mit DB+`.env`)
- [ ] `pytest --cov=src` → ≥ 97 % Gesamt, `assessment`/`alarm`/`api` je 100 %
- [ ] `test_contract_enum_sync.py` grün
- [ ] Guard-Tools (hardcoded thresholds, RB-01) sauber
- [ ] Vorfall-Tests (4) grün
- [ ] Live-E2E: `/v1/health` = ok, `/v1/assessment/current` liefert korrekte Ampel für mind. GRÜN+ROT
- [ ] Fail-safe: STALE/FAULT → `unknown` (nie grün)
- [ ] Alarm-Subsystem: `GET /v1/alarms`, `POST /v1/alarms/{id}/ack` (200), Double-Ack (409)
- [ ] Audit-Log schreibt (`assessment_made`, `alarm_raised`, `alarm_acknowledged`)

Erst wenn alle Haken drin sind, ist „V1 ist verifiziert" eine belastbare Aussage.

---

*Stand: 2026-06-29 · Lebendes Dokument. Ändert sich der Stack, eine Schwelle oder der Contract, dieses
Manual nachziehen (Kopplung via `Abhaengigkeiten.md`).*
