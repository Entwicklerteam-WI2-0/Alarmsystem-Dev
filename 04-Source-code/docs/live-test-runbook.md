# Live-Test-Runbook — G2-Backend lokal testen (MariaDB + G1-Sim)

> **Zweck:** Das laufende Backend gegen eine **lokale MariaDB** und den **G1-Simulator**
> durchspielen — „Input → Ampel", **ohne echte Sensor-Hardware**. Für die Test-Tasks des Teams.
>
> **Verwandte Doku (maßgeblich):** DB aufsetzen → [`dev-db-setup.md`](dev-db-setup.md) (Source of Truth
> für Installation/Pfade) · Sim-Details → [`../tools/g1_sim/README.md`](../tools/g1_sim/README.md) ·
> Schwellen → [`../config/thresholds.json`](../config/thresholds.json).
>
> **Sicherheitsbezug:** Fail-safe **NF-01** (bei Stale/Defekt/Ausfall nie GRÜN) und die
> 4-Stufen-Kaskade (DTB-38) werden hier live geprüft. Die erwarteten Ampeln unten gelten gegen die
> **aktuelle `config/thresholds.json`**; ändert sich dort ein Grenzwert, Grenzfall-Szenarien neu kalibrieren.

---

## TL;DR — drei Komponenten, drei Terminals

```
1) MariaDB :3306   ->  siehe dev-db-setup.md (Server starten)
2) G1-Sim  :9101   ->  .\.venv\Scripts\python.exe tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json
3) Backend :8000   ->  powershell -ExecutionPolicy Bypass -File .\tools\run-local.ps1
```
Prüfen: <http://127.0.0.1:8000/v1/assessment/current> · Szenario wechseln: `tools/g1_sim/g1_state.json` editieren (Sim liest bei jedem Request neu) — **aber Sprung-Guard beachten, siehe §3**.

---

## 0. Einmalige Voraussetzungen

**MariaDB lokal** (nativ, kein Docker — E-35): komplett nach [`dev-db-setup.md`](dev-db-setup.md) aufsetzen
(Installation, DB `alarmsystem`, User `app` + `alarm`, Schema + Grants einspielen). Die dort beschriebenen
zwei Gotchas (`'alarm'@'%'` für TCP statt `'localhost'`; auf MariaDB 11.4.x `REVOKE`→`1064`, mit `--force`)
müssen berücksichtigt sein. **Diese Doku ist die Source of Truth für Pfade und Startbefehle** — dieses
Runbook dupliziert sie bewusst nicht.

**Python-Umgebung** (aus `04-Source-code/`):
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

**`.env` für den Live-Test** (aus `04-Source-code/`, aus `.env.example` ableiten). ⚠️ Die `.env.example`-Defaults
sind auf den **Produktivbetrieb** ausgelegt (`G2_ENABLE_SCHEDULER=false`, `G1_BASE_URL=…g1-sensorik.local`) —
für den Live-Test **müssen** diese beiden Werte geändert werden. Minimal nötig:
```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=alarmsystem
DB_USER=alarm
DB_PASSWORD=<dein-dev-pw>
G1_BASE_URL=http://127.0.0.1:9101
G2_ENABLE_SCHEDULER=true
```
Die `.env` wird **nie** committet (NF-07). `run-local.ps1` erzwingt `G2_ENABLE_SCHEDULER`/`G1_BASE_URL`
zusätzlich als Sicherheitsnetz; bei manuellem Start (§1c) musst du sie selbst setzen.

---

## 1. Starten (Reihenfolge: DB → Sim → Backend)

### 1a) MariaDB
Server starten wie in [`dev-db-setup.md`](dev-db-setup.md) beschrieben (Schnellstart A für Windows /
B für Linux). Check: `Test-NetConnection 127.0.0.1 -Port 3306` → `TcpTestSucceeded : True`.

### 1b) G1-Simulator
```powershell
# eigene Shell, aus 04-Source-code/
.\.venv\Scripts\python.exe tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json
```
Existiert `g1_state.json` noch nicht: `Copy-Item tools/g1_sim/g1_state.example.json tools/g1_sim/g1_state.json`.
Check: <http://127.0.0.1:9101/current> liefert ein Snapshot.

### 1c) Backend — ⚠️ `.env` wird NICHT automatisch geladen
Die App liest `DB_HOST` & Co. aus der **Prozess-Umgebung** (kein `load_dotenv` im Code). Ohne gesetzte
Variablen antwortet `/v1/assessment/current` mit `503` (im **Server-Log** steht die Ursache
`Umgebungsvariable fehlt oder ist leer: DB_HOST`). Zwei Wege:

**Komfort (empfohlen)** — lädt `.env` und erzwingt die Live-Test-Defaults:
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-local.ps1        # Port 8000
```
**Manuell (bash/Git-Bash):**
```bash
DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=alarmsystem DB_USER=alarm DB_PASSWORD=<dev-pw> \
G1_BASE_URL=http://127.0.0.1:9101 G2_ENABLE_SCHEDULER=true \
  python -m uvicorn src.main:app --port 8000
```
> **`G2_ENABLE_SCHEDULER=true`** ist Pflicht — sonst pollt das Backend den Sim nicht (Endpoint bleibt `503`).

---

## 2. Schnelltest

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/health             # {"status":"ok"}
Invoke-RestMethod http://127.0.0.1:8000/v1/assessment/current # risk_level + Messwerte
```
Beim Start steht im Log `Kein threshold_set in der DB -> JSON-Seed-Config (config/thresholds.json)` — das
ist **normal** (die `threshold_set`-Tabelle ist leer, die App nutzt `config/thresholds.json` als Fallback).
Steht dort dagegen `threshold_set nicht lesbar` (WARNING), ist das ein echtes Zeichen: Schema fehlt / DB nicht erreichbar.

---

## 3. Szenarien durchspielen

`tools/g1_sim/g1_state.json` editieren → nach **einem Poll-Zyklus** (≤ 30 s) zeigt
`/v1/assessment/current` die neue Ampel. State-Felder: siehe [`g1_sim/README.md`](../tools/g1_sim/README.md).

> ⚠️ **Sprung-Guard zwischen Szenarien (wichtig!):** Das Backend verwirft Readings mit > 5 °C/min als
> Sensordefekt. Jeder Wechsel mit größerem Temperatursprung (z. B. GRÜN 15 °C → GELB 0,5 / ORANGE −0,5 /
> ROT −2) wird **verworfen**, die Ampel ändert sich dann **nicht**. Für einen sauberen Wechsel daher
> **DB leeren UND Backend neu starten** (siehe §5) — und den Ziel-State **vor** dem ersten Poll setzen.
> Ein Neustart allein reicht **nicht**, weil der Poller die Sprung-Baseline aus der DB nachlädt; die DB
> muss wirklich leer sein. Nur kleine Schritte (≤ 2,5 °C/Poll, z. B. ORANGE ↔ ROT) gehen ohne Reset.

| Szenario | `surface_temp_c` / `air_temp_c` / `humidity_pct` (+Flags) | erwartete Ampel | Stand |
|---|---|---|---|
| **GRÜN** | `15 / 16 / 40` | `green` | ✅ verifiziert |
| **GELB** | `0.5 / 2 / 70` | `yellow` (T_s ≤ 1 °C) | logisch eindeutig |
| **ORANGE** | `-0.5 / -0.5 / 97` | `orange` (T_s ≤ 0, ΔT≈0,4 ≤ 1) | ✅ verifiziert |
| **ROT** | `-2 / -1 / 98` | `red` + **CRITICAL-Alarm** (nach 60 s) | ✅ verifiziert |
| **STALE** | `age_s: 300` | `unknown`, `is_stale:true` (greift nach ~120 s) | erwartet (NF-01) |
| **FAULT** | `status: "fault"` | `unknown` (greift nach ~120 s) | erwartet (NF-01) |
| **G1-DOWN** | `health_down: true` | `unknown` (greift nach ~120 s; `503`, falls nie Daten) | erwartet (NF-01) |

**Die Kaskade** (Quelle: `src/assessment/core.py`, Schwellen aus `config/thresholds.json`):
- **ROT** — `T_s ≤ 0 °C` **und** `ΔT ≤ 0` (ΔT = T_s − Taupunkt; G2 berechnet den Taupunkt aus `air_temp_c`+`humidity_pct`).
- **ORANGE** — `T_s ≤ 0 °C` **und** Feuchte (`ΔT ≤ 1`), aber noch nicht am Taupunkt.
- **GELB** — `T_s ≤ 1 °C` **oder** 30-min-Prognose droht Gefrieren.
- **GRÜN** — sonst (nur bei bekanntem Taupunkt; sonst Fail-safe → mind. GELB).

---

## 4. Stolperfallen (wichtig fürs Testen)

1. **`.env` nicht automatisch geladen** → Variablen setzen (siehe 1c) bzw. `run-local.ps1` nutzen.
   Symptom: `503`; im Server-Log `Umgebungsvariable fehlt oder ist leer: DB_HOST`.
2. **`.env.example`-Defaults sind Produktiv** (`G2_ENABLE_SCHEDULER=false`, `G1_BASE_URL=…g1-sensorik.local`).
   Wer `.env` 1:1 daraus kopiert und **manuell** startet, bekommt ein still totes System (kein Poll → `503`).
   `run-local.ps1` fängt beides ab; beim manuellen Start selbst korrigieren.
3. **Sprung-Guard (`> 5 °C/min`)** → siehe Kasten in §3. Szenariowechsel = DB leeren + Neustart.
4. **Hysterese / Entprellung (ISA-18.2):** Der Alarm kommt erst nach **60 s** stabiler Bedingung
   (`on_delay_s`), die Rückstufung erst nach **300 s** (`downgrade_stable_s`). Kein Bug — Flatter-Schutz.
5. **Fail-safe braucht Zeit:** STALE/FAULT/DOWN schlagen erst nach dem **Stale-Timeout (~120 s)** in
   `unknown` um, weil das zuletzt gültige Reading erst veralten muss. Vorher zeigt der Endpoint den
   letzten guten Wert. (Frischer Start ohne je gültige Daten → `503`.)
6. **PowerShell-ExecutionPolicy:** `.ps1` direkt aufrufen scheitert bei „Restricted". Daher immer
   `powershell -ExecutionPolicy Bypass -File .\tools\run-local.ps1`.

---

## 5. DB zurücksetzen / Stoppen

**Messwerte/Bewertungen leeren** (für einen sauberen Szenariowechsel; privilegierter User `app` aus
`dev-db-setup.md`; `--protocol=tcp` wegen der `-h127`-CLI-Falle):
```powershell
& "<mariadb-bin>\mariadb.exe" --host=127.0.0.1 --protocol=tcp -u app -p alarmsystem `
  -e "SET FOREIGN_KEY_CHECKS=0; TRUNCATE alarm; TRUNCATE assessment; TRUNCATE reading; SET FOREIGN_KEY_CHECKS=1;"
```
> `reading`/`assessment` sind im Betrieb append-only (NF-09); `TRUNCATE` als privilegierter User ist **nur**
> für lokale Tests gedacht, nicht für eine echte Umgebung.

**Prozesse stoppen:** Backend-/Sim-Fenster schließen, oder den Listener auf dem Port beenden:
```powershell
(Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

---

*Stand: 2026-06-28 · Bezug: DTB-17/23 (G1/G3-Integration), G1-Sim (PR #144), NF-01, DTB-38. Lebendes Dokument — bei Schwellen-/Setup-Änderung nachziehen.*
