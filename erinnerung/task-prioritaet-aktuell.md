# Task-Priorität & Reihenfolge nach Architektur-Tiefenaudit (2026-06-26)

> Ableitung aus `architektur-tiefenaudit-2026-06-26.md` + Jira-Bestand (DTB-1…64). Präzisiert die Reihenfolge
> aus `02-Arbeitsdokumente/Tasks+Projektplan.md` angesichts des **REAL-Stands** („Motor gebaut, nicht verdrahtet").
> **Parallele Stränge sind erlaubt und markiert.** Owner = aktueller Jira-Assignee.

> **🔗 DTB-38 ↔ DTB-64:** DTB-38 (4-Stufen-Bewertungslogik) ist **fertig + korrekt** (Jira „Done") → steht hier
> bewusst nicht. Die *Verdrahtung* dieser Logik in einen laufenden Pfad ist **DTB-64** (der Engpass unten). Der
> Code-Kommentar „verdrahtet in DTB-38" meint genau diese Verdrahtung = DTB-64, nicht das (erledigte) DTB-38-Ticket.

## Leitprinzip — der eine Flaschenhals

Der kritische Pfad hat **einen Engpass: die Laufzeit-Verdrahtung (DTB-64).** Bis sie steht, ist fast alles
bereits gebaute Material (Poller, Kaskade, Fail-safe, Audit-Log) **toter Code**. Deshalb gilt: **erst den
Engpass freimachen**, dann öffnen sich mehrere parallele Stränge gleichzeitig.

**Lesehilfe:** 🔴 = kritischer Pfad (seriell, blockt nachgelagertes) · 🟢 = Parallel-Strang · ⛔ = blockiert von.
**Erledigt-Haken:** ✅ = nach `main` gemergt + Jira „Erledigt" · ⏳ = umgesetzt, sitzt in offenem PR (Review/Merge offen) · ◻️ = offen/nicht begonnen.

---

## ✅ Status-Update 2026-06-27 (nach Merge-Welle — Architekt)

> Reconciliation gegen `main` (HEAD `262b246`) + Jira-Board. Yesterday's Merge-Welle hat den **Engpass
> DTB-64 freigemacht und den kompletten kritischen Pfad bis M2-Kern abgeräumt.** Erledigt-Haken siehe unten.

**✅ Gemergt + Jira „Erledigt" gesetzt (heute abgeglichen):**
- **DTB-43** `GET /v1/assessment/current` — PR #108 · *(war Jira „Wird überprüft")*
- **DTB-41** Integrationstest Ingest→Bewertung→API — PR #111 · *(war „Zu erledigen")*
- **DTB-49** Fail-safe-Test (Stale/Defekt → nie GRÜN) — PR #111 · *(war „Zu erledigen")*
- **DTB-62** `GET /v1/thresholds` — PR #99 · *(war „Wird überprüft")*
- **DTB-58** Poller-Stale (>120 s) — PR #93 · *(war „Wird überprüft")*

**✅ War bereits Jira „Erledigt" (kein Eingriff):** DTB-27 (#107), DTB-48 (#109), DTB-29, DTB-32, DTB-60, DTB-13.

**⏳ Umgesetzt, sitzt noch in OFFENEM PR — NICHT auf „Erledigt" (bleibt „Wird überprüft"):**
- **DTB-33** 30-min-Prognose-Producer (FA-06) → **PR #110** offen
- **DTB-63** Write-Auth schreibende `/v1`-Endpoints (NF-07) → **PR #116** offen
- **DTB-64** Health-Contract-Polish (`GET /v1/health` → Health-Schema + 503) → **PR #114** offen
  *(Kern-Verdrahtung von DTB-64 läuft bereits über #105/#108/#111; nur der Health-Feinschliff ist offen → Ticket bleibt bis #114-Merge „Wird überprüft")*
- **Ohne DTB-Ticket** (Infra/Doku): **PR #113** ruff-format-CI-Gate · **PR #115** Doku-Qualitäts-Review · **PR #117** Erinnerung Arash

**→ M2-Kern erreicht:** T0-Slice läuft E2E (`GET /v1/assessment/current` live), NF-01 zur Laufzeit durch
DTB-41/49 nachgewiesen. Damit ist die in diesem Dokument als Top-Priorität markierte Schwelle genommen.

---

## ✅ Status-Update 2026-06-28 (DTB-34 `GET /v1/readings` — Architekt)

**DTB-34 (Strang B, B3) umgesetzt + intern review-freigegeben** (lokal, noch UNGEPUSHT):
- **Repository:** neue Methode `get_readings(sensor_id?, start?, end?, limit, order)` auf dem `Repository`-ABC
  + InMemory + PyMySQL (`ReadingRepository`); geteilter Validator `_validate_readings_query` (Whitelist `order`,
  `limit>0`, tz-aware Grenzen). SQL injection-sicher (parametrisierte Werte, gewhitelistete ORDER-Richtung,
  code-literale Spalten) — von 3 Reviewern unabhängig bestätigt.
- **Endpoint:** `GET /v1/readings` in `src/api/v1.py` gegen die **eingefrorene `openapi.yaml`** gebaut
  (`from`/`to`/`sensor_id`/`limit`[1..1000]/`order`[asc,desc]). Contract-konform: 400/503 als
  `Error {code, message}` (nie FastAPIs `{detail}`), `Cache-Control: no-store`. RB-01 rein lesend, NF-01 nicht
  berührt (Historie, kein Ampelpfad). `bad_request()`-Helper in `responses.py` ergänzt; additives `503` in der
  `openapi.yaml` für `/v1/readings` (T1, nachjustierbar).
- **Qualität:** TDD (RED→GREEN); volle Suite **669 grün / 27 skip**, ruff check+format clean, `api/v1.py`+
  `responses.py` **100 %** Cov, `openapi.yaml` valide. **Review-Loop:** 3 Subagenten (python/fastapi/security,
  kein CRITICAL/HIGH) + Overseer `uni-review-orchestrator` → **FREIGABEREIF**.
- **Offen (Lucas):** Branch-Hygiene (Änderung liegt aktuell mit der `feat/db-finalisierung-real-mariadb`-Arbeit
  im Working Tree — vor PR ggf. auf eigenen `feat/dtb-34-*`-Branch trennen) → PR/Merge → DTB-34 Jira auf „Wird
  überprüft"/„Erledigt". **Follow-up (kein DTB-34-Scope):** seam-weiter `RequestValidationError`-Handler, damit
  FastAPIs Default-422 `{detail}` bei Typ-Fehl-Input (`limit=abc`) ebenfalls als `Error {code,message}` kommt.

---

## Abhängigkeits-Übersicht (auf einen Blick)

```
JETZT sofort startbar (klein, parallel — entblocken den Engpass):
   P0-a Config poll_interval_s ┐
   P0-b Wire-Schemas           ┤──┐  ✅ aufgegangen in DTB-64/DTB-43 (gemergt)
   P0-c AssessmentRepository   ┘  │ (alle drei entblocken DTB-64)
                                  ▼
          ✅/⏳ DTB-64  Runtime-Verdrahtung + AssessmentService + NF-01-Enforcement   ◀── ENGPASS FREI
                                  │   (Kern gemergt #105/#108/#111 · Health-Polish #114 offen)
            ┌─────────────────────┼───────────────────────────────┐
            ▼                     ▼                                ▼
     ✅ DTB-43            🟢 STRANG A: Alarme              🟢 STRANG B: Prognose/Ingest
     assessment/current   ✅ DTB-27 → ◻️ AlarmRepo →        ⏳ DTB-33 (#110), ◻️ DTB-13✅/20,
            │              ◻️ DTB-31 / DTB-61 / DTB-24       ◻️ DTB-34, F24-Geo
            ▼
     ✅ DTB-41 + ✅ DTB-49   Integrationstest E2E + Fail-safe-Test (PR #111)
            │
            ▼
         ✅ M2-Slice lauffähig: Kernprodukt erreichbar, NF-01 bewiesen   ◀── ERREICHT
```

---

## Phase 0 — JETZT sofort (parallel, klein, kein Blocker) — entblockt den Engpass

Drei abhängigkeitsfreie Mini-Tasks. **Parallel an verschiedene Leute** — sie sind die Voraussetzung für DTB-64/DTB-43.

> **Status:** Phase 0 ist mit der DTB-64-/DTB-43-Merge-Welle (#105/#108) **aufgegangen** — die drei
> Mini-Tasks waren Voraussetzungen und sind im gemergten Code enthalten. `AssessmentCurrent`/`Error`/`Health`
> existieren, `AssessmentRepository` ist verdrahtet. (`on_delay`-Platzhalter bewusst abgelehnt → Lucas-Log.)

| ID | Task | Owner-Vorschlag | Status |
|---|---|---|---|
| **P0-a** 🟢 | Config-Feld `poll_interval_s` (+ Platzhalter `on_delay`/`hysterese`) in Schema + `thresholds.json` | Petzold (Teil DTB-64) | ✅ (in DTB-64-Kern) |
| **P0-b** 🟢 | Wire-Schemas als Pydantic: `AssessmentCurrent` (is_stale, sensor_status, measured_at, assessed_at), `AckRequest`, `Error`, `Health` | Ganter | ✅ (via DTB-43 #108) |
| **P0-c** 🟢 | `AssessmentRepository` (F10) — Assessment-Persistenz | Leon H (DB) | ✅ (verdrahtet, DTB-64/#108) |

---

## Phase 1 — Kritischer Pfad: T0-Slice lauffähig 🔴 (seriell)

| # | Status | ID | Task | Owner | ⛔ blockiert von |
|---|---|---|---|---|---|
| 1 | ✅/⏳ | **DTB-64** | Runtime-Verdrahtung: Scheduler (Lifespan/asyncio) + **AssessmentService** + DI in `main.py`; **NF-01-Enforcement** (Stale/Fault → unknown, nie GRÜN); Audit-Log verdrahten · *Kern gemergt (#105/#108/#111); Health-Polish offen (#114)* | **Petzold** | P0-a/b/c |
| 2 | ✅ | **DTB-43** | `GET /v1/assessment/current` (flach, Contract-Form) · *PR #108 gemergt* | **Ganter** | DTB-64, P0-b |
| 3 | ✅ | **DTB-41** + **DTB-49** | Integrationstest Ingest→Bewertung→API **+** Fail-safe-Test (Stale/Defekt → nie GRÜN) · *PR #111 gemergt* | Lucas / Petzold / Amelie | DTB-43 |

→ **Meilenstein M2-Kern: ✅ ERREICHT.** T0-Slice läuft E2E, Kernprodukt erreichbar, NF-01 nachgewiesen.
**Das war die Top-Priorität — abgeräumt.** (Verbleib: Health-Polish #114 mergen, dann DTB-64 → „Erledigt".)

---

## Phase 2 — STRANG A: Alarme 🟢 (startet, sobald DTB-64 steht — parallel zu DTB-43)

Hängt nur an DTB-64 (Service erzeugt Bewertung), **nicht** an DTB-43. Kann also parallel zum Serving-Endpoint laufen.

| # | Status | ID | Task | Owner | ⛔ |
|---|---|---|---|---|---|
| A1 | ✅ | **DTB-27** | Alarm-Erzeugung (Severity aus RiskLevel: ORANGE→warning/ROT→critical) **+ Hysterese/Entprellung** im AssessmentService · *PR #107 gemergt, Jira „Erledigt"* | Petzold | DTB-64 |
| A2 | ◻️ | *(neu)* | `AlarmRepository` (Alarm + Acknowledgement persistieren) | offen → Lucas/Leon H | DDL existiert |
| A3 | ◻️ | **DTB-31** | `GET /v1/alarms` (Resync/Zustand) | Lucas | A2 |
| A4 | ◻️ | **DTB-61** | `GET /v1/alarms/stream` (SSE; Heartbeat, Last-Event-ID) | Petzold | A2 |
| A5 | ◻️ | **DTB-24** | `POST /v1/alarms/{id}/ack` (operator Pflicht, 409 Double-Ack, Audit) | Lucas | A2, P0-b (AckRequest), DTB-29-Wiring |

A3/A4/A5 sind nach A2 untereinander parallel.

---

## Phase 2 — STRANG B: Prognose & Ingest-Härtung 🟢 (parallel zu Strang A)

| # | Status | ID | Task | Owner | Hinweis |
|---|---|---|---|---|---|
| B1 | ⏳ | **DTB-33** | 30-min-Trendprognose **Producer** (FA-06) — Konsumentenseite in `core.py` ist fertig · *umgesetzt, **PR #110 offen** (Review/Merge)* | Leon H | **FA-06 = Pflicht für M3**, nicht „nice to have" |
| B2 | ◻️ | **DTB-13** ✅ + **DTB-20** | `check_plausibility` (Flatline/Sprung) in den Ingest-Pfad **einbinden** (existiert, nie aufgerufen) · *DTB-13 erledigt; DTB-20-Wiring „In Arbeit"* | Andi / Leon H | klein, hoher Effekt (Defekt-Erkennung aktiv) |
| B3 | ⏳ | **DTB-34** | `GET /v1/readings` Historie (T1) — **umgesetzt + Overseer-FREIGABEREIF** (s. Status-Update 28.06.); PR/Merge offen | Lucas (impl.) | war „niedrigere Dringlichkeit" |
| B4 | ◻️ | *(F24)* | Geoposition in Config | offen | klein, niedrig |

B1/B2 können sofort nach DTB-64 starten; B3/B4 sind nachrangig.

---

## Phase 3 — Sicherheit, Integration & Abschluss 🟢 (Richtung M3, nach Kern)

| Status | ID | Task | Owner | Hinweis |
|---|---|---|---|---|
| ✅ | **DTB-62** | `GET /v1/thresholds` (PR #99 gemergt) — **Contract-Erweiterung mit G3 klären** (nicht im Freeze) | Arash | Code erledigt; **offene Naht-Entscheidung (deine) bleibt** |
| ⏳ | **DTB-63** | Auth-/Credential-Konzept für schreibende `/v1`-Endpoints (NF-07) · *umgesetzt, **PR #116 offen*** | Arash | für DTB-24/Config-Schreiben |
| ✅ | **DTB-48** | ADR Fail-safe Multi-Layer-Architektur (dokumentiert die NF-01-Schichten) · *PR #109 gemergt* | Lucas | begleitend zu DTB-64 |
| ◻️ | **DTB-42** | RB-01-Nachweis finalisieren — **Audit bestätigt bereits sauber** (kein Aktor) · *Jira „In Arbeit"* | Amelie | nur noch Nachweis-Doku |
| ◻️ | **DTB-17 / DTB-23** | E2E-Integration mit G1 / G3 | Lucas | M3 |
| ◻️ | **DTB-30 / DTB-44** | Testprotokoll / Abschlusspräsentation + Demo | Amelie / Landmann | M3 |
| ◻️ | **DTB-36 / DTB-40 / DTB-47** | Entscheidungslogbuch + Reflexion/Methodenvergleich | Petzold / Landmann | M3, **menschlich** (40 %) |

> **Nebenbefund (kein DTB-Ticket, in Review):** **DTB-29** Audit-Log ist bereits Jira „Erledigt"; offene Infra-/Doku-PRs
> **#113** (ruff-format-CI-Gate), **#115** (Doku-Qualitäts-Review), **#117** (Erinnerung) sind reviewbereit.

---

## „Wer kann wann starten" — Parallelisierungs-Fahrplan

> **Aktualisiert 27.06.:** Der Engpass DTB-64 ist **frei** — DTB-43 + Integrationstests sind gemergt (M2-Kern erreicht).
> Strang A und Strang B sind damit **offen und parallel startbar**.

- **✅ Erledigt (Engpass + kritischer Pfad):** P0-a/b/c, DTB-64-Kern, DTB-43, DTB-41+49 — alle auf `main`.
- **Jetzt offen, parallel (3–4 Leute):**
  - **Strang A (Alarme):** zuerst **A2 `AlarmRepository`** (DDL existiert), dann parallel DTB-31 / DTB-61 / DTB-24.
  - **Strang B:** **DTB-33 (#110) mergen** (FA-06, Pflicht für M3) · **DTB-20** Plausibility-Wiring in den Ingest-Pfad.
- **Kurzfristig wegräumen (offene PRs):** #114 (DTB-64 Health-Polish → dann DTB-64 „Erledigt"), #110 (DTB-33), #116 (DTB-63), #113/#115/#117 (Infra/Doku).
- **Deine offene Architekten-Entscheidung:** DTB-62 `/v1/thresholds` = Contract-Erweiterung außerhalb des v1-Freeze → Naht mit G3 (Nick) klären.
- **Nicht vergessen:** FA-06 (DTB-33) ist **Pflicht**, kein Bonus — sitzt reviewbereit in #110.

---

*Quelle: Tiefenaudit 2026-06-26 (Run `wf_53434d4b-97a`). Lebende Priorisierung — bei Statuswechsel/neuer Naht aktualisieren.
Synchron halten mit `02-Arbeitsdokumente/Tasks+Projektplan.md` (P0–P6) und dem Jira-Board.*
*Letzter Status-Abgleich: 2026-06-27 (Merge-Welle → M2-Kern erreicht; Jira DTB-41/43/49/58/62 → Erledigt). —architekt*
