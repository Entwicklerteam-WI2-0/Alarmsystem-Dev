# Fahrplan DTB-64 + DTB-27 — Stand nach Runde 3

> Zusammenführung aus [`task-prioritaet-nach-audit-2026-06-26.md`](task-prioritaet-nach-audit-2026-06-26.md) und [`architektur-tiefenaudit-2026-06-26.md`](architektur-tiefenaudit-2026-06-26.md).  
> Ziel: Transparenz darüber, was seit dem Tiefenaudit bereits umgesetzt ist (PR #105) und was DTB-27 (#107) noch anbinden muss.

**Legende:** ✅ erledigt · 🔴 kritischer Pfad (blockt nachgelagertes) · 🟢 parallel möglich · ⛔ wartet auf

---

## DTB-64 — Runtime-Verdrahtung + AssessmentService + NF-01 (PR #105)

| # | Task | Status | Bemerkung / Bezug Audit |
|---|---|:---:|:---|
| 1 | `AssessmentService.assess_reading` mit Assess-Zeit-NF-01 (None/Fault/Stale → `unknown`, nie GRÜN) | ✅ | Schließt Audit-Finding F07 NF-01-Invarianten (Teil) |
| 2 | `build_assessment_current` mit Serve-Zeit-NF-01 (Stale/Fault → `unknown` + Messwerte genullt) | ✅ | Schließt Audit-Finding F07 Serve-Zeit-Schicht |
| 3 | `AssessmentRepository` Interface + `InMemory` + `MySqlAssessmentRepository` (parametrisiert) | ✅ | Schließt Audit-Finding F10 Assessment-Persistenz |
| 4 | Wire-Schemas: `AssessmentCurrent`, `Health`, `Error`, `AckRequest` | ✅ | Schließt Audit-Finding F15 Schemas (Teil) |
| 5 | Runtime/DI in `main.py`: `build_runtime`, `lifespan`, `run_scheduler`, `Poller` | ✅ | Schließt Audit-Finding DTB-38 Orchestrierung (Grundgerüst) |
| 6 | Audit-Log `assessment_made` best-effort verdrahtet | ✅ | Schließt Audit-Finding F13 Audit-Log (Teil) |
| 7 | Runde-3-Fixes: Orphan-Row-Edge-Case (`_insert` ID-Check vor commit) in Assessment + Reading Repo | ✅ | Vermeidet halb persistierte Zeilen ohne ID |
| 8 | Runde-3-Test: negatives `delta_t` (Eisrisiko → ROT) für Service-Pfad | ✅ | Ergänzt den rein GRÜN-Gutpfad-Test |
| 9 | Tests: 363 passed, 14 skipped, ruff clean | ✅ | Stand nach Push `8ad6dfe` |
| 10 | **🔴 DTB-43:** `GET /v1/assessment/current` einkommentieren & testen | ⬜ | Gerüst liegt auskommentiert in `main.py`; blockiert E2E-Test |
| 11 | `GET /v1/health` auf Pydantic `Health` + 503-Pfad heben | ⬜ | Audit-Finding F17 |
| 12 | `poll_interval_s` aus Config statt Env/Default | ⬜ | P0-a aus Prioritätsdatei |
| 13 | E2E-Integrationstest Ingest → Bewertung → API (DTB-41/49) | ⬜ | Audit-Finding T0-Slice |

### Nächste Aktionen für DTB-64
1. DTB-43 Endpoint aktivieren (einkommentieren, mit `build_assessment_current` verdrahten, 503-Pfade testen).
2. Health-Endpoint auf Pydantic + 503-Pfad anheben.
3. PR #105 final reviewen/mergen.

---

## DTB-27 — Alarm-Generierung + Severity + Hysterese (PR #107)

| # | Task | Status | Bemerkung |
|---|---|:---:|:---|
| 1 | Severity-Ableitung (`ORANGE→warning`, `ROT→critical`) | ✅ | In PR #107 |
| 2 | Auslöse-Hysterese / On-Delay | ✅ | In PR #107 |
| 3 | Anzeige-Rückstufung (`RiskHysterese`) | ✅ | In PR #107 |
| 4 | `AlarmRepository` (save-only, parametrisiert) | ✅ | In PR #107 |
| 5 | `alarm_service` mit Audit `alarm_raised` | ✅ | In PR #107 |
| 6 | Hysterese-Parameter in `thresholds.json` + `loader.py` | ✅ | In PR #107 |
| 7 | Tests: 353 passed, 11 skipped, 100 % Coverage auf DTB-27-Modulen | ✅ | In PR #107 |
| 8 | **🔴 Verdrahtung Poll-Loop → `AlarmService.evaluate(assessment)`** | ⬜ | Folge-Task nach Merge von #105 + #107 |
| 9 | `GET /v1/alarms` (DTB-31) | ⬜ | Abhängig von A2/A3 |
| 10 | `GET /v1/alarms/stream` SSE (DTB-61) | ⬜ | Abhängig von A2/A3 |
| 11 | `POST /v1/alarms/{id}/ack` (DTB-24) | ⬜ | Abhängig von A2/A3 + AckRequest |

### Nächste Aktionen für DTB-27
1. PR #107 reviewen/mergen (nach #105, weil DTB-27 fachlich auf Assessment aufbaut).
2. Nach dem Merge beider PRs: kleiner Folge-PR, der `assess_reading` mit `AlarmService` verdrahtet.

---

## Merge-Reihenfolge & kritische Abhängigkeiten

```
#105 (DTB-64)  ──┐
                 ├──→  Folge-PR: Poll-Loop → AlarmService.evaluate()
#107 (DTB-27)  ──┘
```

- **#105 zuerst** — liefert Assessment-Service + Runtime-Gerüst.
- **#107 danach** — Alarm-Logik baut auf Assessments auf; bei Merge-Reihenfolge #107 vor #105 wäre die Alarm-Logik ohne produktiven Konsumenten.
- **Kein harter Dateikonflikt** erwartet: #107 erweitert `loader.py`/`thresholds.json` um `hysterese`; #105 nutzt nur die bestehenden Sektionen (`vereisung`, `prognose`, `datenqualitaet`).

---

## Offene Audit-Findings, die nach den beiden PRs noch bestehen

- `check_plausibility` (Flatline/Sprung) ist weiterhin **toter Code** — muss in den Ingest-Pfad eingebunden werden (DTB-13/20, Strang B).
- 30-min-Prognose Producer fehlt (FA-06, DTB-33, Strang B).
- Auth-/Credential-Konzept für schreibende Endpoints (NF-07, DTB-63, M3).
- `GET /v1/readings` Historie (DTB-34, niedrigere Dringlichkeit).

---

*Letzte Aktualisierung: 2026-06-26 nach Push `8ad6dfe` auf `feat/dtb-64-scaffold`.*
*Synchron halten mit: `task-prioritaet-nach-audit-2026-06-26.md`, `architektur-tiefenaudit-2026-06-26.md`.*
