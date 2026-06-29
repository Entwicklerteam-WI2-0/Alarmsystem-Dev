# Task-Priorität & Reihenfolge — REAL-Stand nach Code (2026-06-27)

> **Aktualisiert gegen den echten Code auf `origin/main` (HEAD `a55c075`).**
> Keine Vermutungen, keine Erinnerung — alle Einträge gegen `git log`, `gh pr list`,
> `pytest` und die tatsächlichen Source-Dateien geprüft.
>
> Standort dieser Datei: `erinnerung/task-prioritaet-aktuell.md` (Non-Code, lebende
> Priorisierung). Synchron halten mit Jira und `02-Arbeitsdokumente/Tasks+Projektplan.md`.

## TL;DR — Gesamtlage

- **Backend-Prototyp ist technisch funktional komplett.**
- **Keine offenen PRs mehr** auf GitHub.
- **Tests:** 794 passed, 36 skipped, Coverage 94,55 %.
- **Verbleibend:** DTB-54 DoD (Pi-MariaDB-Init), Git-Tag `api-v1.0`, menschliche
  M3-Deliverables (Testprotokoll, Demo, Reflexion/Entscheidungslogbuch), Live-Integration G1/G3.

---

## Was tatsächlich auf `origin/main` gemergt ist

| DTB | PR | Inhalt | Status |
|---|---|---|---|
| DTB-38 | — | 4-Stufen-Vereisungsbewertung (`src/assessment/core.py`) | ✅ |
| DTB-43 | #108 | `GET /v1/assessment/current` | ✅ |
| DTB-41 | #111 | E2E-Integrationstest Ingest → Bewertung → API | ✅ |
| DTB-49 | #111 + #135 | Fail-safe-Tests (Stale/Defekt → nie GRÜN) + vollständige Schichten-Integrationstests | ✅ |
| DTB-62 | #99 | `GET /v1/thresholds` | ✅ |
| DTB-63 | #130 | Write-Auth für schreibende `/v1`-Endpoints | ✅ |
| DTB-64 | #105/#108/#111 + #114 | Runtime-Verdrahtung, Scheduler, Health-Contract | ✅ |
| DTB-27 | #107 | Alarm-Erzeugung + Hysterese/On-Delay | ✅ |
| DTB-31 | #140 | `GET /v1/alarms` (Resync/Zustand) | ✅ |
| DTB-61 | #123 | `GET /v1/alarms/stream` (SSE, Heartbeat, Last-Event-ID) | ✅ |
| DTB-24 | #132 | `POST /v1/alarms/{id}/ack` (Quittierung, 409 Double-Ack, Audit) | ✅ |
| DTB-34 | #131/#133 | `GET /v1/readings` Historie | ✅ |
| DTB-33 | #119 | 30-min-Prognose-Producer (FA-06) | ✅ |
| DTB-20 | #128/#138 | Defekt-Erkennung + Plausibilitäts-Wiring im Ingest-Pfad | ✅ |
| DTB-53–56 | #129 | Reale MariaDB-Verifikation (DB-Finalisierung) | ✅ |
| DTB-66 | #136 | `driving_factor`/`explanation` in `AssessmentCurrent` | ✅ |
| DTB-48 | #109 | ADR Fail-safe Multi-Layer-Architektur | ✅ |
| DTB-42 | — | RB-01-Nachweis: Code audit-sauber (kein Aktor-Endpoint) | ✅ |
| DTB-29 | — | Audit-Log verdrahtet | ✅ |

**→ Meilenstein M2 ist vollständig abgeschlossen.**

---

## v1-API-Endpoints im Code (`src/api/v1.py` + `src/main.py`)

| Endpoint | Methode | Status | Anmerkung |
|---|---|---|---|
| `/v1/health` | GET | ✅ | `Health{status:"ok"}` / 503 |
| `/v1/assessment/current` | GET | ✅ | Fail-safe NF-01: Stale/Fault → `unknown`, nie GRÜN |
| `/v1/thresholds` | GET | ✅ | Aktive Schwellen lesen |
| `/v1/thresholds` | POST | ✅ | Auth: `Authorization: Bearer <G2_API_KEY>` |
| `/v1/readings` | GET | ✅ | Historie mit `from`/`to`/`sensor_id`/`limit`/`offset`/`order` |
| `/v1/alarms` | GET | ✅ | Resync/Zustand (kein Entdeckungs-Poll) |
| `/v1/alarms/stream` | GET | ✅ | SSE-Live-Stream mit Heartbeat |
| `/v1/alarms/{id}/ack` | POST | ✅ | Quittierung, reine UI-/Audit-Aktion (RB-01) |

---

## Module im Code (`src/`)

| Modul | Inhalt | Status |
|---|---|---|
| `ingest/` | Poller gegen G1, Eingangsvalidierung, Stale/Defekt-Erkennung | ✅ |
| `model/` | Pydantic-Schemas + Enums (Reading, Assessment, Alarm, Ack, ThresholdSet, Audit) | ✅ |
| `assessment/` | 4-Stufen-Bewertung, Fail-safe, Service, Utils | ✅ |
| `alarm/` | Severity-Mapping, Hysterese/On-Delay, Alarm-Generierung | ✅ |
| `storage/` | Repository-Pattern, rohes PyMySQL, Alarm/Ack/Audit/Assessment/Reading/ThresholdSet | ✅ |
| `api/` | v1-Router, Runtime, Security, Responses, Broadcaster, Exceptions | ✅ |
| `config/` | Parametrierbare Schwellen (`thresholds.json`) + Loader | ✅ |
| `forecast/` | 30-min-T_s-Prognose (Trend + Bridge) | ✅ |

---

## Was noch offen ist

| ID | Task | Owner | Status | Nächster Schritt |
|---|---|---|---|---|
| DTB-54 | MariaDB-Init auf Pi — DoD-Nachweis (6 Tabellen, Grants, Idempotenz, append-only) | Andreas / Leon H | ❌ offen | Manuelle Verifikation auf dem Pi durchführen und dokumentieren |
| — | Git-Tag `api-v1.0` setzen (letzter mechanischer Schritt laut `API_FROZEN_v1.md`) | Lucas | ❌ offen | `git tag api-v1.0 a55c075 && git push origin api-v1.0` |
| DTB-30 | Testprotokoll finalisieren | Amelie | ❌ offen | Menschliches M3-Deliverable |
| DTB-44 | Demo-Skript / Abschlusspräsentation | Amelie / Landmann | ❌ offen | Menschliches M3-Deliverable |
| DTB-36/40/47 | Entscheidungslogbuch + Reflexion/Methodenvergleich | Petzold / Landmann | ❌ offen | **40 %-Einzelleistung**, menschlich |
| DTB-17/23 | E2E-Live-Integration mit G1 / G3 | Lucas | ❌ offen | Gegen echte Sensor-API + Frontend testen |

---

## Technische Kennzahlen (aktueller Stand)

- **Tests:** 794 passed, 36 skipped, 1 Warning (Starlette-Deprecation `httpx`)
- **Coverage:** 94,55 % (Ziel ≥ 80 % für Bewertungslogik deutlich übertroffen)
- **Lint/Format:** ruff check + ruff format — clean
- **Offene PRs:** 0
- **Offene GitHub-Issues:** unbekannt (nicht geprüft)
- **Hinweis:** Einige Tests sind ge-skipped, weil sie eine echte DB/G1-Verbindung oder
  bestimmte Env-Vars benötigen. Das ist beabsichtigt, kein Fehler.

---

## Empfohlene nächste Aktionen

1. **DTB-54 abschließen** — Pi-MariaDB-Init mit dem DoD-Nachweis aus der README.
2. **Git-Tag `api-v1.0` setzen** — Contract-Freeze offiziell markieren.
3. **Testprotokoll + Demo-Skript** erstellen (Amelie / Landmann).
4. **Entscheidungslogbuch/Reflexion** von den Studierenden selbst verfassen (40 %).
5. **Live-Integration G1/G3** vorbereiten und durchführen.

---

*Quelle: Reale Bestandsaufnahme vom 2026-06-27 gegen `origin/main` (HEAD `a55c075`).*
*Worktree: `C:/Users/luceb/.worktrees/Alarmsystem-Dev-stand-docs`.*
*Letzte Prüfung: 794 Tests grün, 94,55 % Coverage, ruff clean, 0 offene PRs.*

---

## 🔌 Hinweis — G1-Naht-Sim für live-nahe Tests (28.06., architekt)
Für **„Input → Ampel"-Tests gegen die G1-Naht ohne echte Sensor-Hardware**: steuerbarer **G1-Sensor-Simulator**
unter `04-Source-code/tools/g1_sim/` (**PR #144**). Bedient den konsumierten G1-Contract (`GET /current` + `/health`);
Szenario per State-Datei **live umschaltbar** (grün/rot/stale/fault/down), kein Neustart. Start + Szenario-/Erwartungs-Tabelle:
`tools/g1_sim/README.md`. Devs testen gegen `main` mit lokaler MariaDB (`04-Source-code/docs/dev-db-setup.md`)
→ `feat/`-Branch → PR → Lucas merged.
**Real-Test 28.06. bestätigt:** voller Pfad Poll→Bewertung→Persistenz→Serving→Alarm→Ack→**Fail-safe NF-01** läuft E2E
gegen echte MariaDB 11.4.7; 785 Tests grün (siehe Journal/Save-Session 28.06.).

---

## 📌 Offene DTB-Tickets — Restarbeit nach Jira-Reconciliation (Stand 28.06., gegen `main`)

> Nach der Merge-Welle sind **alle Kern-Backend-Tickets** auf `main` + Jira „Erledigt"
> (DTB-20/24/31/33/34/59/63/64/66/68). Was bleibt: M3-Arbeit (Integration vor Ort + menschliche
> Doku/Reflexion) + ein paar additive Follow-ups.

**🔴 Integration / vor Ort (Mo 29.06., Pi):**
- **DTB-17** — E2E-Integration mit **G1** (echte/sim Sensordaten) — Brücke: G1-Sim `tools/g1_sim/`
- **DTB-23** — E2E-Integration mit **G3** (Frontend konsumiert API)
- **DTB-57** — Pi-Betrieb: Retention/Rotation `reading` + `audit_log` (SD-Karten-Schutz)

**🟠 Architektenentscheidung (Lucas):**
- **DTB-39** — Betriebsmodell + Latenz-Zielwert festlegen (AE-01/NF-02)
- **DTB-67** — G3-Abstimmung: `driving_factor`/`explanation` auf `unknown`-Antworten (das „stale"-Label bei Fault/Down)

**🟡 Additive Code-Follow-ups (kein Blocker):**
- **DTB-65** — `threshold_set_id` im Assessment-Snapshot protokollieren (NF-05) — Infra steht, Service setzt es noch `None` (greift nach erstem `POST /v1/thresholds`)
- **DTB-69** — Flatline-Parameter (`flatline_epsilon_c`/`flatline_timeout_min`) gegen finale G1-Sensorauflösung nachkalibrieren
- **DTB-37** — Restliche Messgrößen (RH, Druck) — im `Reading`-Model bereits vorhanden → nur Verifikation/Abschluss

**🟣 Menschlich / M3-Abgabe (NICHT KI):**
- **DTB-30** — Testprotokoll (Abnahme-Checkliste)
- **DTB-36** — Gruppen-Entscheidungslogbuch finalisieren
- **DTB-42** — RB-01-Nachweis (kein Aktor) — Audit bestätigt sauber, nur Nachweis-Doku
- **DTB-44** — Abschlusspräsentation + Demo-Skript
- **DTB-45** — Individuelle Entscheidungsreflexion je Person
- **DTB-47** — Reflexion: Methodenvergleich Wasserfall vs. Scrum

**⚪ Borderline — faktisch erledigt, Jira-Status prüfen/schließen:**
- **DTB-21** — pytest-Konfiguration + Fixtures (existiert, 785 Tests laufen)
- **DTB-46** — Unit-Tests Bewertung ≥ 80 % Coverage (assessment ~100 %, erfüllt)

*Quelle: Jira-Board (Projekt DTB) reconciled gegen `origin/main` am 2026-06-28; 10 gemergte Tickets auf „Erledigt" gesetzt.*

---

## ✏️ Korrektur/Update (28.06., nach DTB-37/65-Klärung) — architekt

- **DTB-37 (RH/Druck): ERLEDIGT** — `humidity_pct` + `pressure_hpa` sind im `Reading`-Model + Poller, persistiert + im Assessment. War oben fälschlich „Borderline". → Jira „Erledigt".
- **DTB-65 (threshold_set_id / NF-05): umgesetzt → PR #148** — Service stempelt jetzt den aktiven `threshold_set` auf **jedes** Assessment (Gutfall + Fail-safe), `None` bei JSON-Seed. (war „offen")
- **DTB-67 — wartet auf G3 (Nick):** der Code füllt `driving_factor`/`explanation` auf `unknown` bereits („stale"); die **Abstimmung**, ob das so passt, geht nur mit G3 → morgen vor Ort. **Heute nicht lösbar.**
- **DTB-69 — BLOCKIERT durch G1 (Nils):** braucht die finale DS18B20-Auflösung (Bit-Tiefe + echte Zappelbreite); aktueller `flatline_epsilon_c=0.15` ist ein dokumentierter Schätzwert. **Heute nicht lösbar.**
- **DTB-36 — menschliche M3-Doku:** Gruppen-Entscheidungslogbuch konsolidieren (Abgabe-Deliverable), kein Backend-Code.

---

## ✏️ Update (28.06. abends, nach Tiefenverifikation + Deep Review) — orga

**Vollständige Live- + DB-Verifikation durchgeführt** (erstmals mit echter lokaler MariaDB, nicht nur InMemory).

**Neue Kennzahlen (gegen `origin/main` + lokaler DB):**
- **Tests: 832 passed, 0 failed, 0 skipped** (vorher: 794 passed / 36 skipped — die 36 Skips waren die DB-Integrationstests, die jetzt alle laufen).
- **Coverage: 98 %** (vorher 94,55 %).
- **ruff check + format: clean.**
- Beide Guard-Tools grün (Hardcode-Schwellen, RB-01-Aktor-Check).

**Verifikationsergebnisse:**
- **V1 vertragskonform: JA** (Subagent-Tiefenaudit). Alle 8 Routen registriert, Schemas/Enums/Status-Codes stimmen mit `API_FROZEN_v1.md`/`openapi.yaml` überein, kein RB-01-Verstoß, keine hardcodierten fachlichen Schwellen.
- **Live-Durchstich E2E** (G1-Sim → Poller → Bewertung → DB → API → Alarm → Ack): alle Szenarien korrekt — GRÜN/ROT+CRITICAL/STALE→unknown/FAULT→unknown/Double-Ack 409. Audit-Log schreibt sauber (82 Einträge live bestätigt).

**Neuer PR offen:**
- **PR #156** (`test/vorfaelle-integration`): 2 neue Integrationstests für die dokumentierten Vorfälle auf Service-Ebene (Persistenz + Audit + ΔT-in-Explanation-Assertion). Ergänzt die vorhandenen Unit-Tests. 832 Tests grün. Wartet auf Reviewer (Arezo/Amelie).

**Deep Engineering-Review (Subagent, belastbar):**
- Note-Tendenz: **Sehr gut (1,0–1,3)** für WI-2, *sofern die mündliche Reflexion dieselbe Tiefe zeigt*.
- 5 Schwächen, alle MEDIUM/LOW, **keine CRITICAL/HIGH**: (1) Kommentardichte, (2) `main.py` wächst (565 Zeilen), (3) `grants.sql` hardkodierter DB-Name/User, (4) kein Connection-Pooling, (5) `ack` ohne Auth (bewusst M2) + CORS `*`.
- Reifester Pfad bis Abgabe: Kommentar punktuell konsolidieren, `main.py`-Split, Live-Demo üben, `grants.sql`/Env abstimmen.

**Priorität M3 (verschiebt sich durch verifizierten Stand):**
1. **Reflexions-/Entscheidungsdoku (40 % Einzelleistung)** — jetzt höchste Priorität, da Code verifiziert verlässlich ist. Die 5 Schwächen als bewusste Ingenieursentscheidungen aufbereiten = direkt Zahlung auf die Note.
2. **PR #156 reviewen + mergen.**
3. **DTB-17/23** E2E-Live-Integration G1/G3 (G1-Sim steht bereit).
4. **DTB-54** Pi-MariaDB-Init DoD-Nachweis (lokal verifiziert, auf Pi wiederholen).
5. **Git-Tag `api-v1.0`** setzen.
6. Menschliche M3-Deliverables (Testprotokoll, Demo, Präsentation).

*Quelle: Live-Verifikation 28.06. abends gegen `origin/main` + lokale MariaDB 11.4.7; Subagent-Tiefenaudit + Deep Review.*
