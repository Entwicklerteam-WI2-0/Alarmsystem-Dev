# Architektur-Tiefenaudit — 2026-06-26

> **Werkzeug:** `uni:architektur-tiefenaudit` (Architekt, read-only) · **Orchestrierung:** Workflow-Maximal,
> 23 Subagenten (10 Subsystem-Traces via `code-explorer` → je adversariale Gegenprobe + 3 Spezial-Linsen:
> `silent-failure-hunter`/NF-01, RB-01-Aktor, Contract-Treue). Run `wf_53434d4b-97a`, ~18 min, 2,18 Mio Tokens.
> **Scope:** ausschließlich lokaler `main` (HEAD `6ca916f`). Offene PRs (#99 DTB-62) zählen NICHT als Code.
> **Soll-Quelle:** `Usecase-quick.md` (FA/NF/RB), eingefrorener Contract `openapi.yaml`/`API_FROZEN_v1.md`,
> `Schwellenwerte.md` (Kaskade). Schwellen sind DUMMY bis G1 → geprüft wurde **Parametrierbarkeit**, nicht die Zahlen.

---

## GESAMT-VERDIKT: Liefert das Backend das Produkt? **NEIN (noch nicht) — „Motor gebaut, nicht verdrahtet".**

Der `main`-Stand besteht aus **hochwertigen, gut getesteten Einzelmodulen** (reine Funktionen + Repositories),
die aber **fast nirgends zu einem laufenden Produkt zusammengeschaltet sind**. `src/main.py` ist ein
19-Zeilen-Stub mit genau **einem** Endpoint (`GET /v1/health`). Es gibt **keinen Scheduler, keinen
Assessment-Orchestrator, keine Serving-Schicht, kein Alarm-Subsystem**. Die zentrale Integrationsarbeit
**(DTB-38 „Verdrahtung")** ist nicht gelandet — der `is_stale`-Kommentar im Code sagt es wörtlich:
*„bevor is_stale in DTB-38 verdrahtet wird"* (`tests/test_storage_repository.py`).

Das ist ein **stimmiger, erklärbarer Zustand**, kein Chaos: bottom-up gebaut, top-down noch nicht integriert.
Aber als **lauffähiges Endprodukt durchläuft heute nichts** end-to-end.

**Headline-Zahl (25 geprüfte Features):** ~2 ✅ · ~12 ⚠️ vorhanden-aber-kaputt/unverdrahtet · ~11 ❌ fehlt.
**Findings:** 11 CRITICAL · 23 HIGH · 23 MEDIUM · 22 LOW. **RB-01 (kein Aktor): sauber gewahrt.**

---

## Vollständigkeits-Matrix (Soll → Ist, nach Subsystem)

Legende: ✅ vorhanden+korrekt · ⚠️ vorhanden, aber kaputt/unverdrahtet · ❌ fehlt

| Subsystem | Feature | Verdikt | Kern-Befund (Beleg) |
|---|---|:--:|---|
| **Ingest** | F01 Poller GET /current 30s | ⚠️ | Poller korrekt, aber **nie instanziiert** — kein Scheduler in `main.py`. Poll-Intervall existiert nicht als Parameter (`poller.py:42`, `main.py:1-19`). |
| | F02 Stale-Detection | ⚠️ | Zwei korrekte Stale-Schichten (Ingest-Zeit `poller.py:195-202`; Serve-Zeit `failsafe.py:28`) — letztere **nirgends aufgerufen**. |
| | F03 Sensor-Defekt | ⚠️ | 3–5 Checks im Poller verdrahtet (fault, Out-of-Range, NaN, Clock-Skew); **Flatline/Sprung in `failsafe.check_plausibility()` toter Code** (nie aufgerufen). |
| | F04 G1-Health getrennt | ⚠️ | `_is_g1_healthy()` korrekt vor `/current`, sauber getrennt (`poller.py:77-130`) — aber Poller läuft nie. |
| **Bewertung** | F05 Taupunkt + ΔT | ⚠️ | Magnus korrekt (`utils.py:71`); `dew_point_c` via Poller verdrahtet, aber ΔT+Kaskade laufen nie. |
| | F06 4-Stufen-Kaskade | ⚠️ | Kaskade korrekt + erster-Treffer + Schwellen aus Config (`core.py:27-91`), **aber `assess_ice_risk` wird von keinem Live-Modul aufgerufen**. |
| | F08 Hysterese/Entprellung | ❌ | Komplett absent — `assess_ice_risk` ist zustandslos, kein Timer/On-Delay (`core.py:3-4`). |
| **Fail-safe** | F07 NF-01-Invarianten | ⚠️ | `is_stale`/`build_unknown_assessment` korrekt, **aber zur Laufzeit unenforced** (kein Caller); `assess_ice_risk` hat keinen internen stale/fault-Guard. |
| **Persistenz** | F09 Reading-Persistenz | ✅ | **Vollständig + korrekt verdrahtet**: parametrisiert, append-only, vom Poller aufgerufen, DB-Fehler → `RepositoryError` (`repository.py:115-186`). |
| | F10 Assessment-Persistenz | ❌ | Kein `AssessmentRepository`, kein INSERT, kein Caller (`storage/__init__.py`). |
| **Audit** | F13 Audit-Log | ⚠️ | `AuditRepository` append-only korrekt + getestet, **aber auf `main` komplett unverdrahtet** — kein Ereignis wird je geschrieben (`audit_repository.py`). |
| **Alarme** | F11 Erzeugung | ❌ | Kein assessment→alarm-Übergang, keine Severity-Ableitung. Nur Schemas existieren. |
| | F12 Ack + Double-Ack | ❌ | Kein Endpoint, kein 409-Pfad. |
| | F18 GET /v1/alarms | ❌ | Route fehlt. |
| | F19 SSE /v1/alarms/stream | ❌ | Kein SSE, kein StreamingResponse. |
| | F20 POST .../ack | ❌ | Route fehlt. |
| **API /v1** | F16 assessment/current | ❌ | **Kernprodukt fehlt** — nicht registriert (`main.py:1-19`, `api/__init__.py` = leerer Stub). |
| | F17 GET /v1/health | ⚠️ | Existiert, aber `dict[str,str]` statt Pydantic `Health`, **kein 503-Pfad** (`main.py:16-19`). |
| | F21 GET /v1/readings (T1) | ❌ | Route fehlt. |
| **Datenmodell** | F15 Schemas/Enums | ⚠️ | Enums **vollständig+korrekt**; aber **`AssessmentCurrent`, `AckRequest`, `Error`, `Health` fehlen als Pydantic-Modelle**; `id`-Felder optional, fehlende `maxLength`. |
| **Config** | F14 Parametrierbarkeit | ⚠️ | Loader/Thresholds/`ConfigError` solide; `poll_interval`/`on_delay`/Hysterese fehlen (bewusster Scope, `thresholds.json:_scope`); `load_thresholds()` **nie in `main.py` aufgerufen**. |
| | F24 Geoposition | ❌ | Kein geo-Eintrag in Config. |
| **Prognose** | F23 30-min-Vorwarnung | ⚠️ | Konsumentenseite (GELB-Ast in `core.py`) bereit, **Produzent fehlt** — `forecast/` ist leerer Namespace. FA-06 ist Pflicht. |
| **Sicherheit** | F22 RB-01 kein Aktor | ✅ | **Sauber** — kein Freigabe-/Sperr-/Steuer-Pfad im gesamten Baum (Aktor-Linse: 0 Treffer). |
| | F25 NF-07 Auth | ❌ | Nicht implementiert (geplant M3, AE-02 offen). |

---

## Die zentrale Diagnose — Pfad-/Dependency-Befunde

**Ein Wurzelproblem erklärt 6 der 11 CRITICALs:** `main.py` assembliert **keinen Dependency-Injection-Graph**.
Es gibt keinen Lifespan-Handler, keinen `asyncio`-Task, keinen Scheduler, keinen Assessment-Service. Folge —
fünf vollständig implementierte Subsysteme sind zur **Laufzeit toter Code**:

- **Poller** wird nie instanziiert → kein Ingest, keine Persistenz-Befüllung, keine Defekt-Erkennung aktiv.
- **`assess_ice_risk`** (Kaskade) wird nie aufgerufen → keine Bewertung entsteht.
- **`is_stale` / `build_unknown_assessment` / `check_plausibility`** (Fail-safe) werden nie aufgerufen.
- **`AuditRepository`** wird nie aufgerufen → kein einziges der 6 Audit-Ereignisse wird geschrieben.
- **`load_thresholds()`** wird in `main.py` nie aufgerufen.

Einzige **vollständig verdrahtete** Kette: `Poller.poll() → ReadingRepository.save()` (F09) — die ist aber
ihrerseits ohne Scheduler nie aktiv. **Die T0-Slice (Poller → Persistenz → Bewertung → `GET /v1/assessment/current`)
ist an 3 von 4 Nähten gebrochen.**

> **Gute Nachricht:** Die Bausteine sind hochwertig. `migrations/schema.sql` enthält bereits **`alarm`- und
> `acknowledgement`-Tabellen** (`schema.sql:56-78`) — die DB-Schicht für Alarme ist also DDL-seitig fertig,
> der Blocker ist allein die Python-Schicht. Das ist überwiegend **Integrations- und Serving-Arbeit, nicht
> Neuentwicklung von Logik.**

---

## Fail-safe (NF-01) & RB-01 — Integrität

- **RB-01 (kein Aktor): ✅ gewahrt.** Aktor-Linse fand **keinen** Freigabe-/Sperr-/Steuer-Pfad im Baum. Treffer
  wie `open`/`close` betreffen ausschließlich DB-Connections/Files. (Alarm-Ack existiert ohnehin nicht.)
- **NF-01 (nie GRÜN bei Stale/Fault): ⚠️ auf dem Papier korrekt, zur Laufzeit unenforced.** Die Linse
  `silent-failure-hunter` urteilt **FAIL**: Alle Bausteine existieren, aber kein laufender Endpoint ruft sie.
  Zusatzrisiken für die spätere Verdrahtung:
  - `assess_ice_risk()` hat **keinen internen stale/sensor_status-Guard** (`core.py:27-91`) — gibt GRÜN zurück,
    sobald die Physik passt. NF-01 hängt damit allein am (noch fehlenden) Orchestrator. **Beim Verdrahten MUSS
    der Service stale/fault VOR `assess_ice_risk` prüfen und `unknown` erzwingen.**
  - `sensor_status=fault` wird im Poller **verworfen statt gespeichert** (`poller.py:177-179`) → die DB enthält
    nur `ok`-Readings; eine Serve-Zeit-Schicht kann `fault` aus der DB nicht ableiten. **Architektur-Frage fürs
    Serving.**

---

## Contract-Treue (/v1 vs. `openapi.yaml`) — Linse: **kritisch unterimplementiert**

**1 von 6** eingefrorenen Endpoints existiert (`GET /v1/health`), und der hat 2 Abweichungen:

| Contract-Endpoint | Status auf `main` |
|---|---|
| `GET /v1/health` | ⚠️ vorhanden, aber `dict` statt `Health`-Schema, **kein 503-Pfad** |
| `GET /v1/assessment/current` | ❌ fehlt (Kernprodukt) — `AssessmentCurrent`-Schema existiert nicht einmal |
| `GET /v1/readings` | ❌ fehlt |
| `GET /v1/alarms` | ❌ fehlt |
| `GET /v1/alarms/stream` (SSE) | ❌ fehlt |
| `POST /v1/alarms/{id}/ack` | ❌ fehlt (`AckRequest`-Schema fehlt) |

> **Hinweis zur Naht:** PR #99 (offen) fügt `GET /v1/thresholds` hinzu — **nicht im eingefrorenen Contract**.
> Das ist eine bewusste Contract-Erweiterung, die separat als Naht-Entscheidung (mit G3) zu klären ist
> (steht schon offen). Der Audit wertet sie nicht als „Drift", da nicht auf `main`.

---

## Priorisierte Lücken-Liste — Baureihenfolge zum lauffähigen Produkt

1. **[CRITICAL] DTB-38 — Orchestrierung/DI in `main.py`.** Lifespan/Scheduler, der den Poller periodisch ruft;
   ein **Assessment-Service**, der nach jedem Reading verbindet: `is_stale`/`sensor_status` prüfen →
   `assess_ice_risk` **oder** `build_unknown_assessment` → persistieren → Audit schreiben. Entkoppelt 6 CRITICALs auf einmal.
2. **[CRITICAL] Serving-Layer `/v1`.** `GET /v1/assessment/current` + **`AssessmentCurrent`-Schema**
   (`is_stale`, `sensor_status`, `measured_at`, `assessed_at`); `GET /v1/health` als Pydantic + 503; `GET /v1/readings`.
3. **[CRITICAL] NF-01-Enforcement zur Laufzeit.** Der Assessment-Service erzwingt „nie GRÜN bei Stale/Fault".
   Ohne das ist die ganze Fail-safe-Logik nur Bibliothek. + Serve-Zeit-`fault`-Ableitung lösen.
4. **[CRITICAL] Alarm-Subsystem.** Severity-Ableitung (ORANGE→warning/ROT→critical), `AlarmRepository`
   (DDL existiert), `/v1/alarms` + SSE-Stream + `POST .../ack` (409 Double-Ack, `AckRequest`-Schema).
5. **[HIGH] F10 Assessment-Persistenz** (`AssessmentRepository`).
6. **[HIGH] F23/FA-06 30-min-Prognose** — Producer (Trend-Extrapolation); FA-06 ist **Pflicht** (Vorlauf ≥30 min).
7. **[HIGH] F08 Hysterese/Entprellung** + `poll_interval`/`on_delay` als Config-Felder; `check_plausibility`
   (Flatline/Sprung) in den Ingest-Pfad einbinden.
8. **[MEDIUM] Vorfall-2-Test korrigieren** — `test_vorfall_2` nutzt ΔT=+0,2 → ORANGE statt ROT; der benannte
   Vorfall-Test deckt das Spec-Szenario (ΔT≤0) **nicht** ab (kritischer-Pfad-DoD, team-os §7).
9. **[MEDIUM] Datenmodell-Feinschliff** — `Error`/`Health`/`AckRequest`-Schemas, `maxLength`-Constraints,
   `id`-Felder für Responses absichern; Exception-Handler `{code,message}`.
10. **[MEDIUM] No-Hardcode-Guard** auf `src/ingest`+`src/api` ausweiten (aktuell nur assessment/forecast).
11. **[geplant M3] NF-07 Auth** (AE-02).

---

*Read-only Audit — keine Code-/Doc-Änderung. Befunde + `datei:zeile` an den Architekten (Lucas), der entscheidet
und fixt. Voll-Datensatz (79 Findings, Feature-Matrix, Skeptiker-Korrekturen) im Workflow-Run `wf_53434d4b-97a`.*
