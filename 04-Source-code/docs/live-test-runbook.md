# Live-Test-Runbook — G2-Backend lokal testen (MariaDB + G1-Sim)

> **Zweck:** Das laufende Backend gegen eine **lokale MariaDB** und den **G1-Simulator**
> durchspielen — „Input → Ampel", **ohne echte Sensor-Hardware**. Für die Test-Tasks des Teams.
>
> **Verwandte Doku:** DB-Aufsetzen → [`dev-db-setup.md`](dev-db-setup.md) · Sim-Details →
> [`../tools/g1_sim/README.md`](../tools/g1_sim/README.md) · Schwellen → `../config/thresholds.json`.
>
> **Sicherheitsbezug:** Fail-safe **NF-01** (bei Stale/Defekt/Ausfall nie GRÜN) und die
> 4-Stufen-Kaskade (DTB-38) werden hier live geprüft. Die erwarteten Ampeln unten gelten gegen
> die **aktuelle `config/thresholds.json`**; ändert sich dort ein Grenzwert, Grenzfall-Szenarien neu kalibrieren.

---

## TL;DR — drei Komponenten, drei Terminals

```
1) MariaDB :3306   ->  C:\Users\<dein-user>\mariadb-portable\start-mariadb.bat
2) G1-Sim  :9101   ->  python tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json
3) Backend :8000   ->  tools/run-local.ps1            (laedt .env + startet uvicorn)
```
Prüfen: <http://127.0.0.1:8000/v1/assessment/current> · Szenario wechseln: `tools/g1_sim/g1_state.json` editieren (Sim liest bei jedem Request neu, **kein** Neustart).

---

## 0. Einmalige Voraussetzungen

**MariaDB** lokal (nativ, kein Docker — E-35). Vollständig in [`dev-db-setup.md`](dev-db-setup.md).
Zwei Stolpersteine, die schon berücksichtigt sein müssen:
- `grants.sql` vergibt an `'alarm'@'localhost'` — bei TCP (`127.0.0.1`) zusätzlich `'alarm'@'%'`, sonst `ERROR 1142`.
- Auf MariaDB **11.4.x** werfen die `REVOKE`-Zeilen `1064` → mit `--force` einspielen, die `GRANT`s sitzen korrekt.

**Python-Umgebung** (aus `04-Source-code/`):
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

**`.env`** anlegen (aus `.env.example`) und die DB-Zugangsdaten eintragen — `DB_HOST=127.0.0.1`,
`DB_USER=alarm`, `DB_PASSWORD=<dein-dev-pw>`, `DB_NAME=alarmsystem`. Die `.env` wird **nie** committet (NF-07).

---

## 1. Starten (Reihenfolge: DB → Sim → Backend)

### 1a) MariaDB
```powershell
C:\Users\<dein-user>\mariadb-portable\start-mariadb.bat
```
Check: `Test-NetConnection 127.0.0.1 -Port 3306` → `TcpTestSucceeded : True`.

### 1b) G1-Simulator
```powershell
# eigene Shell, aus 04-Source-code/
.\.venv\Scripts\python.exe tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json
```
Existiert `g1_state.json` noch nicht: `Copy-Item tools/g1_sim/g1_state.example.json tools/g1_sim/g1_state.json`.
Check: <http://127.0.0.1:9101/current> liefert ein Snapshot.

### 1c) Backend — ⚠️ `.env` wird NICHT automatisch geladen
Die App liest `DB_HOST` & Co. aus der **Prozess-Umgebung** (kein `load_dotenv` im Code). Ohne gesetzte
Variablen antwortet `/v1/assessment/current` mit `503: Umgebungsvariable fehlt: DB_HOST`. Drei Wege:

**Komfort (empfohlen):**
```powershell
.\tools\run-local.ps1            # laedt .env in die Umgebung und startet uvicorn auf :8000
```
**Manuell (PowerShell):**
```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^\s*([^#][^=]*)=(.*)$') { Set-Item ("env:" + $matches[1].Trim()) $matches[2].Trim() } }
$env:G2_ENABLE_SCHEDULER = "true"
.\.venv\Scripts\python.exe -m uvicorn src.main:app --port 8000
```
**Manuell (bash/Git-Bash):**
```bash
DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=alarmsystem DB_USER=alarm DB_PASSWORD=<dev-pw> \
G1_BASE_URL=http://127.0.0.1:9101 G2_ENABLE_SCHEDULER=true \
  python -m uvicorn src.main:app --port 8000
```
> **`G2_ENABLE_SCHEDULER=true`** ist für den Live-Test Pflicht — sonst pollt das Backend den Sim nicht.

---

## 2. Schnelltest

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/health             # {"status":"ok"}
Invoke-RestMethod http://127.0.0.1:8000/v1/assessment/current # risk_level + Messwerte
```
Beim Start steht in den Logs `threshold_set nicht lesbar -> JSON-Seed-Config` — das ist **normal**:
die `threshold_set`-Tabelle ist leer, die App nutzt `config/thresholds.json` als Fallback.

---

## 3. Szenarien durchspielen

`tools/g1_sim/g1_state.json` editieren → nach **einem Poll-Zyklus** (≤ 30 s) zeigt
`/v1/assessment/current` die neue Ampel. State-Felder: siehe [`g1_sim/README.md`](../tools/g1_sim/README.md).

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

1. **`.env` nicht automatisch geladen** → Variablen setzen (siehe 1c). Symptom: `503 DB_HOST fehlt`.
2. **Sprung-Guard (`> 5 °C/min`)**: Ein direkter GRÜN↔ROT-Sprung (z. B. 15 → −2 °C) wird als
   Sensordefekt **verworfen** — die Ampel ändert sich dann nicht. Für saubere Sprünge:
   **Backend frisch starten + DB leeren** (siehe 5) **oder** die Temperatur in Schritten ≤ 2,5 °C/Poll ändern.
3. **Hysterese / Entprellung (ISA-18.2):** Der Alarm kommt erst nach **60 s** stabiler Bedingung
   (`on_delay_s`), die Rückstufung erst nach **300 s** (`downgrade_stable_s`). Kein Bug — Flatter-Schutz.
4. **Fail-safe braucht Zeit:** STALE/FAULT/DOWN schlagen erst nach dem **Stale-Timeout (~120 s)** in
   `unknown` um, weil das zuletzt gültige Reading erst veralten muss. Vorher zeigt der Endpoint den
   letzten guten Wert. (Frischer Start ohne je gültige Daten → `503`.)

---

## 5. DB zurücksetzen / Stoppen

**Messwerte/Bewertungen leeren** (z. B. für einen sauberen GRÜN↔ROT-Wechsel; als **root**):
```powershell
& "C:\Users\<dein-user>\mariadb-portable\mariadb-11.4.12-winx64\bin\mariadb.exe" -u root alarmsystem `
  -e "SET FOREIGN_KEY_CHECKS=0; TRUNCATE alarm; TRUNCATE assessment; TRUNCATE reading; SET FOREIGN_KEY_CHECKS=1;"
```
> `reading`/`assessment` sind im Betrieb append-only (NF-09); `TRUNCATE` als root ist **nur** für
> lokale Tests gedacht, nicht für eine echte Umgebung.

**Prozesse stoppen:** Backend/Sim-Fenster schließen, oder den Listener auf dem Port beenden:
```powershell
(Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

---

*Stand: 2026-06-28 · Bezug: DTB-17/23 (G1/G3-Integration), G1-Sim (PR #144), NF-01, DTB-38. Lebendes Dokument — bei Schwellen-/Setup-Änderung nachziehen.*
