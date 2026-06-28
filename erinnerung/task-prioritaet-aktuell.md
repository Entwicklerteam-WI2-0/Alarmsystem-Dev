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
