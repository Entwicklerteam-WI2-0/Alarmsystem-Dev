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

---

## Abhängigkeits-Übersicht (auf einen Blick)

```
JETZT sofort startbar (klein, parallel — entblocken den Engpass):
   P0-a Config poll_interval_s ┐
   P0-b Wire-Schemas           ┤──┐
   P0-c AssessmentRepository   ┘  │ (alle drei entblocken DTB-64)
                                  ▼
              🔴  DTB-64  Runtime-Verdrahtung + AssessmentService + NF-01-Enforcement   ◀── ENGPASS
                                  │
            ┌─────────────────────┼───────────────────────────────┐
            ▼                     ▼                                ▼
     🔴 DTB-43            🟢 STRANG A: Alarme              🟢 STRANG B: Prognose/Ingest
     assessment/current     DTB-27 → AlarmRepo →             DTB-33 (FA-06), DTB-13/20,
            │                DTB-31 / DTB-61 / DTB-24          DTB-34, F24-Geo
            ▼
     🔴 DTB-41 + DTB-49   Integrationstest E2E + Fail-safe-Test
            │
            ▼
         ✅ M2-Slice lauffähig: Kernprodukt erreichbar, NF-01 bewiesen
```

---

## Phase 0 — JETZT sofort (parallel, klein, kein Blocker) — entblockt den Engpass

Drei abhängigkeitsfreie Mini-Tasks. **Parallel an verschiedene Leute** — sie sind die Voraussetzung für DTB-64/DTB-43.

| ID | Task | Owner-Vorschlag | Hinweis |
|---|---|---|---|
| **P0-a** 🟢 | Config-Feld `poll_interval_s` (+ Platzhalter `on_delay`/`hysterese`) in Schema + `thresholds.json` | Petzold (Teil DTB-64) | klein |
| **P0-b** 🟢 | Wire-Schemas als Pydantic: `AssessmentCurrent` (is_stale, sensor_status, measured_at, assessed_at), `AckRequest`, `Error`, `Health` | Ganter | schließt Datenmodell-Lücke; nötig für DTB-43/DTB-24 |
| **P0-c** 🟢 | `AssessmentRepository` (F10) — Assessment-Persistenz | Leon H (DB) | DB-DDL existiert bereits in `schema.sql` |

---

## Phase 1 — Kritischer Pfad: T0-Slice lauffähig 🔴 (seriell)

| # | ID | Task | Owner | ⛔ blockiert von |
|---|---|---|---|---|
| 1 | **DTB-64** | Runtime-Verdrahtung: Scheduler (Lifespan/asyncio) + **AssessmentService** + DI in `main.py`; **NF-01-Enforcement** (Stale/Fault → unknown, nie GRÜN); Audit-Log verdrahten | **Petzold** | P0-a/b/c |
| 2 | **DTB-43** | `GET /v1/assessment/current` (flach, Contract-Form) | **Ganter** | DTB-64, P0-b |
| 3 | **DTB-41** + **DTB-49** | Integrationstest Ingest→Bewertung→API **+** Fail-safe-Test (Stale/Defekt → nie GRÜN) | Lucas / Petzold / Amelie | DTB-43 |

→ **Meilenstein M2-Kern:** T0-Slice läuft E2E, Kernprodukt erreichbar, NF-01 nachgewiesen. **Das ist die Top-Priorität.**

---

## Phase 2 — STRANG A: Alarme 🟢 (startet, sobald DTB-64 steht — parallel zu DTB-43)

Hängt nur an DTB-64 (Service erzeugt Bewertung), **nicht** an DTB-43. Kann also parallel zum Serving-Endpoint laufen.

| # | ID | Task | Owner | ⛔ |
|---|---|---|---|---|
| A1 | **DTB-27** | Alarm-Erzeugung (Severity aus RiskLevel: ORANGE→warning/ROT→critical) **+ Hysterese/Entprellung** im AssessmentService | Lucas *(In Arbeit)* | DTB-64 |
| A2 | *(neu)* | `AlarmRepository` (Alarm + Acknowledgement persistieren) | offen → Lucas/Leon H | DDL existiert |
| A3 | **DTB-31** | `GET /v1/alarms` (Resync/Zustand) | Lucas | A2 |
| A4 | **DTB-61** | `GET /v1/alarms/stream` (SSE; Heartbeat, Last-Event-ID) | Petzold | A2 |
| A5 | **DTB-24** | `POST /v1/alarms/{id}/ack` (operator Pflicht, 409 Double-Ack, Audit) | Lucas | A2, P0-b (AckRequest), DTB-29-Wiring |

A3/A4/A5 sind nach A2 untereinander parallel.

---

## Phase 2 — STRANG B: Prognose & Ingest-Härtung 🟢 (parallel zu Strang A)

| # | ID | Task | Owner | Hinweis |
|---|---|---|---|---|
| B1 | **DTB-33** | 30-min-Trendprognose **Producer** (FA-06) — Konsumentenseite in `core.py` ist fertig | Lucas *(In Arbeit)* | **FA-06 = Pflicht für M3**, nicht „nice to have" |
| B2 | **DTB-13** + **DTB-20** | `check_plausibility` (Flatline/Sprung) in den Ingest-Pfad **einbinden** (existiert, nie aufgerufen) | Andi / Leon H | klein, hoher Effekt (Defekt-Erkennung aktiv) |
| B3 | **DTB-34** | `GET /v1/readings` Historie (T1) | Petzold | niedrigere Dringlichkeit |
| B4 | *(F24)* | Geoposition in Config | offen | klein, niedrig |

B1/B2 können sofort nach DTB-64 starten; B3/B4 sind nachrangig.

---

## Phase 3 — Sicherheit, Integration & Abschluss 🟢 (Richtung M3, nach Kern)

| ID | Task | Owner | Hinweis |
|---|---|---|---|
| **DTB-62** | `GET /v1/thresholds` (PR #99) — **Contract-Erweiterung mit G3 klären** (nicht im Freeze) | Arash | offene Naht-Entscheidung (deine) |
| **DTB-63** | Auth-/Credential-Konzept für schreibende `/v1`-Endpoints (NF-07) | Arash | für DTB-24/Config-Schreiben |
| **DTB-48** | ADR Fail-safe Multi-Layer-Architektur (dokumentiert die NF-01-Schichten) | Lucas | begleitend zu DTB-64 |
| **DTB-42** | RB-01-Nachweis finalisieren — **Audit bestätigt bereits sauber** (kein Aktor) | Amelie | nur noch Nachweis-Doku |
| **DTB-17 / DTB-23** | E2E-Integration mit G1 / G3 | Lucas | M3 |
| **DTB-30 / DTB-44** | Testprotokoll / Abschlusspräsentation + Demo | Amelie / Landmann | M3 |
| **DTB-36 / DTB-40 / DTB-47** | Entscheidungslogbuch + Reflexion/Methodenvergleich | Petzold / Landmann | M3, **menschlich** (40 %) |

---

## „Wer kann wann starten" — Parallelisierungs-Fahrplan

- **Sofort (heute):** P0-a, P0-b, P0-c (3 Leute parallel) · plus B2 (Plausibility-Wiring) ist schon jetzt machbar.
- **Sobald DTB-64 gemergt:** DTB-43 **und** ganz Strang A **und** Strang B öffnen sich gleichzeitig (3–4 Leute parallel).
- **Engpass-Warnung:** DTB-64 liegt bei **einer** Person (Petzold) und blockt am meisten → eng begleiten, ggf. zu zweit (Pairing mit Ganter, da DTB-43 direkt anschließt).
- **Nicht vergessen:** FA-06 (DTB-33) ist **Pflicht**, kein Bonus — früh in Strang B einplanen.

---

*Quelle: Tiefenaudit 2026-06-26 (Run `wf_53434d4b-97a`). Lebende Priorisierung — bei Statuswechsel/neuer Naht aktualisieren.
Synchron halten mit `02-Arbeitsdokumente/Tasks+Projektplan.md` (P0–P6) und dem Jira-Board.*
