# Architektur-Tiefenaudit — 2026-06-30

> Read-only Vollaudit des G2-Backends (HEAD `a7ae2a0`). Methode: Workflow `wf_9ab3c11d-0ff`, 32 Agenten,
> 14 Audit-Features aus Source of Truth (Usecase-quick FA/NF/RB, eingefrorene `openapi.yaml`, `Schwellenwerte.md`).
> Pro Feature: `code-explorer`-Tiefen-Trace → adversariale Gegenprobe. Plus 3 Linsen (NF-01, RB-01, Contract).
> Belege als `datei:zeile`. **Der Architekt entscheidet & fixt — dieser Report ändert keinen Code.**

## GESAMT-VERDIKT: Liefert das Backend das Produkt? **JA, mit einer echten HIGH-Lücke.**

**13 / 14 Features grün+korrekt; 1 broken (F11 Audit-Log-Vollständigkeit).** Der kritische Pfad
(Ingest → Bewertungs-Kaskade → Persistenz → Serving → Alarm → SSE → Ack) trägt end-to-end. **NF-01**
(nie GRÜN bei stale/fault) ist am **Serve-Punkt** hart durchgesetzt; **RB-01** (kein Aktor) ist
**vollständig** gewahrt. Kein Datenverlust. Die echte Restarbeit ist Audit-Vollständigkeit (FA-12) plus
einige MEDIUM-Härtungen — mehrere davon bereits als **E-43** bekannt/deferred.

## Vollständigkeits-Matrix

| F# | Feature | Reqs | Vorhanden | Pfad/Deps | Logik | Verdikt | Schlüssel-Beleg |
|---|---|---|---|---|---|---|---|
| F1 | Ingest / G1-Poller (Pull) | FA-09/01/02/03, NF-02/11 | ja | ja | ja | ✅ | `ingest/poller.py`, `main.py:111,247` |
| F2 | Datenqualität (Stale/Defekt/Plausibilität) | FA-04, NF-01 | ja | ja | ja | ✅ | `assessment/failsafe.py`, `poller.py:183,195` |
| F3 | Taupunkt & ΔT (Magnus) | FA-01/05 | ja | ja | ja | ✅ | `assessment/utils.py`, `poller.py:464` |
| F4 | Bewertungs-Kaskade ROT>ORANGE>GELB>GRÜN | FA-05, NF-05/04 | ja | ja | ja | ✅ | `assessment/core.py:99` |
| F5 | Fail-safe NF-01 (nie GRÜN) | NF-01, RB-01 | ja | ja | ja | ✅ | `service.py:131-181,291-322` |
| F6 | Anzeige-Hysterese (Rückstufung) | NF-05/08 | ja | ja | ja | ✅ | `alarm/riskhysterese.py:105-141` |
| F7 | Persistenz / Repository-Pattern | FA-03, NF-11/06 | ja | ja | ja | ✅ | `storage/*`, `database.py` |
| F8 | Alarm-Generierung + On-Delay | FA-08, NF-01 | ja | ja | ja | ✅ | `alarm/{generation,hysterese,service}.py` |
| F9 | SSE-Stream + Resync | FA-08/07, NF-01 | ja | ja | ja | ✅ | `api/broadcaster.py`, `api/v1.py` |
| F10 | Alarm-Quittierung (Ack) | FA-10, RB-01, NF-09 | ja | ja | ja | ✅ | `api/v1.py:512-550`, `acknowledgement_repository.py` |
| **F11** | **Audit-Log (Schreiben+Lesen)** | **FA-12, NF-09** | **partial** | **partial** | **partial** | **⚠️ broken** | **`poller.py:218-236` (kein audit_repo)** |
| F12 | 30-min-Prognose | FA-06 | ja | ja | ja | ✅ | `forecast/{trend,bridge}.py` |
| F13 | Config/Thresholds + Auth-Schreibweg | NF-05, FA-11, NF-07/09 | ja | ja | ja | ✅ | `config/loader.py`, `api/security.py` |
| F14 | Serving-Naht (assessment/current, health, readings, Error) | FA-07/09, NF-01 | ja | ja | ja | ✅ | `main.py:556-621`, `api/responses.py` |

Legende: ✅ vorhanden+korrekt · ⚠️ vorhanden+kaputt · ❌ fehlt.

## Die eine echte Lücke — F11 Audit-Log (FA-12, MUSS, nur 3/4 erfüllt)

- **[HIGH] `reading_ingested` wird in Produktion NIE geschrieben.** Der `Poller` bekommt **kein**
  `audit_repo` (Konstruktor `base_url/repository/thresholds`, `main.py:111-116`); nach `repository.save()`
  wird nur geloggt (`poller.py:218-236`). FA-12 (`Usecase-quick.md:109`: „Protokolliert **MESSWERTE**,
  Bewertungen, Alarme und Quittierungen" — MUSS) ist damit **3/4**. Der eingefrorene Contract bewirbt
  `reading_ingested` gegenüber G3 (`openapi.yaml:958`), aber **kein Producer existiert**.
  Tracer wertete CRITICAL, adversariale Gegenprobe **downgrade auf HIGH**: kein Datenverlust (Readings
  liegen in der `reading`-Tabelle), reine **Audit-Vollständigkeits-/Contract-Lücke**.
- **[HIGH] `sensor_fault` wird nie als `event_type` geschrieben.** Ein Sensor-Fault-Zyklus trägt
  `event_type='assessment_made'` (`service.py:143-153,240-247`), nicht `sensor_fault`. Der Enum-Wert
  (`enums.py:62`) ist toter Code im Schreibpfad.
- **Produkt-Konsequenz:** Der von G3 konsumierte `GET /v1/audit`-Strom (DB-Spiegel) zeigt **nie**
  `reading_ingested`/`sensor_fault` — nur `assessment_made`/`alarm_*`/`threshold_changed`.
- **Fix-Richtung:** `audit_repo` in den `Poller` injizieren, nach erfolgreichem `save()` ein
  `reading_ingested` appenden; bei `status=fault` ein `sensor_fault`-Event. (Klein, lokal, mit Test.)

## Pfad-/Dependency-Befunde (MEDIUM — Härtung, keine Blocker)

- **[MEDIUM] Serve-Zeit-Kohärenz-Loch (latentes Fail-safe-Leck).** `assessment_current` paart
  `assessment_repo.get_latest()` + `reading_repo.get_latest()` als **zwei unabhängige Queries** ohne
  Prüfung `assessment.reading_id == reading.id` (`main.py:596-607`). Bei **partiellem DB-Fehler**
  (Reading gespeichert, Assessment-INSERT scheitert, `main.py:320-321`) kann ein **altes GRÜN-Assessment**
  mit einem **frischen, ok-Reading** ausgeliefert werden → GRÜN trotz inzwischen schlechterer Lage. Eng
  (nur partieller DB-Ausfall), selbstheilend im nächsten Zyklus. Fix: `reading_id`-Join oder Mismatch →
  `is_stale/unknown`.
- **[MEDIUM] Pre-Poll-Zeitstempel-Skew.** `now = datetime.now(UTC)` wird **vor** dem (bis 10 s
  blockierenden) Poll gesetzt (`main.py:246-247`). Ein grenzwertig-stales Reading (115 s bei Timeout 120 s)
  wird assess-zeitlich als frisch bewertet → **GRÜN ins persistierte Assessment** geschrieben. Serve-Zeit
  fängt es (frisches `now`) → ausgeliefert wird `unknown`, aber der **DB-/Audit-Stand** ist falsch. Fix:
  `now` **nach** dem Poll setzen.
- **[MEDIUM] Fault-vs-Stale-Diagnose (= bekannte E-43, accept & defer).** Poller verwirft fault-Readings
  vor der Persistenz (`poller.py:386-389`) → `assess_reading` läuft über den `None`-Zweig →
  `driving_factor='stale'` statt `sensor_fault`; die `FAULT`-Zweige in `service.py:143-155,291-293` sind im
  Single-Poller-Live-Pfad **toter Code**; `sensor_status` am Wire ist im 30-120 s-Fenster fälschlich `ok`.
  **Sicherheit hält** (nie GRÜN). **Bereits als E-43 dokumentiert + deferred** — kein neuer Befund.
- **[MEDIUM] Hysterese-Erklärungstext widerspricht Messwerten.** Bei **gehaltener Rückstufung** ruft
  `derive_explanation` die entprellte Stufe mit den **rohen aktuellen** Messwerten auf (`service.py:205-212`)
  → Text mit falscher Ungleichung („Oberfläche 0.3 °C ≤ 0.0 °C"). Ampel korrekt (konservativ), nur der
  Operator-Text (DTB-66 Explainability) ist transient falsch.

## Fail-safe (NF-01) & RB-01 — Integrität

- **NF-01: Kern-Invariante gehalten.** `build_assessment_current` re-evaluiert `is_stale` mit frischem
  `now` und prüft `reading.status` vor jeder Antwort → über den normalen Poll-Pfad **kann kein GRÜN auf
  stale/fault ausgeliefert werden**. Einschränkungen: das Serve-Zeit-Kohärenz-Loch + der Pre-Poll-Skew
  (beide oben) verschmutzen den **gespeicherten** Assessment-/Audit-Stand, nicht die ausgelieferte Antwort.
  Zusatz: `_write_audit` loggt nur die Exception-Message statt `logger.exception` (Traceback verloren,
  `service.py:249-250`).
- **RB-01: vollständig gewahrt.** Kein Aktor-/Freigabe-/Sperr-/Steuer-Pfad. grep-Treffer
  (`unlock|freigabe|sperr|release|execute|control|actuat`) sind ausnahmslos harmlos (DB `cursor.execute`,
  SSE `reserve/release`, `Cache-Control`, `SELECT … FOR UPDATE`, Flatline-„Sperre", Doku). `ack` = reine
  UI-/Audit-Aktion; Clearing rein manuell; `AlarmState.CLEARED` ist im Produktionscode **schreib-unerreichbar**
  (kein Auto-Clear) — RB-01-konform.

## Contract-Treue (/v1 vs. openapi.yaml)

Alle **9 Endpoints vorhanden**, Methode+Pfad exakt; Fehlerformat `Error{code,message}` auf allen
**dokumentierten** Pfaden konsequent (400 für Query/Pfad, 422 für Body). Drift (Contract eingefroren →
**nur melden, nicht umschreiben**; Korrektur fast immer Spec, nicht Code, = Architektenentscheidung):

- **[MEDIUM] `Thresholds`-Schema nur 4/6 Sektionen** (`hysterese`, `betrieb` fehlen, `openapi.yaml:651-742`).
  POST-Client streng nach Spec → **422** („Pflicht-Abschnitt fehlt: hysterese"); GET liefert 2 undok. Top-Level-Keys.
- **[MEDIUM] 503 undokumentiert** bei `GET /v1/alarms` und `POST /v1/alarms/{id}/ack` (Impl liefert es via
  `RuntimeNotReadyError`/`RepositoryError`; Spec führt es dort nicht — anders als readings/audit).
- **[LOW] `{detail}`-Leck auf undok. Fläche:** kein `StarletteHTTPException`-Handler → 404 auf unbekanntem
  `/v1`-Pfad bzw. 405 (falsche Methode) liefert FastAPIs `{detail}` statt `Error{code,message}` (Contract D).
- **[LOW] `forecast_surface_temp_c`** IST formal abgedeckt (`API_FROZEN_v1.md:59`, `openapi.yaml:862-868`) —
  der irreführende „NICHT Teil des Wire-Contracts"-Kommentar steht am **Storage-Modell** `Assessment`
  (`schemas.py:87-88`), nicht am Wire-Modell (`schemas.py:236-239`). Kommentar klären.
- **[LOW] `GET /v1/thresholds`** zeigt die **beim Start** geladenen Schwellen, nicht den zuletzt per POST
  persistierten Satz (Reload-Semantik DTB-63, bewusst) — ohne Hinweis im Response.

## Priorisierte Lücken-Liste (was für ein vollständiges Produkt fehlt)

1. **[HIGH] FA-12 Audit-Vollständigkeit:** `reading_ingested` + `sensor_fault` produzieren — `audit_repo`
   in den Poller injizieren. Einziger Grund, dass F11 nicht grün ist. (Frozen-openapi bewirbt es, G3-DB-Spiegel
   zeigt es sonst nie.)
2. **[MEDIUM] Serve-Zeit-Kohärenz:** `assessment.reading_id == reading.id` erzwingen (oder Mismatch → unknown).
3. **[MEDIUM] Pre-Poll-Skew:** `now` nach dem Poll setzen, damit kein GRÜN-Assessment für ein grenzwertig-stales Reading persistiert wird.
4. **[MEDIUM] Hysterese-Erklärungstext** auf displayed-konsistente Werte bringen (Operator-Vertrauen).
5. **[MEDIUM] Thresholds-Contract-Drift** (4→6 Sektionen) + undok. 503 auf alarms/ack → **Spec ergänzen**
   (Architektenentscheidung; Code ist korrekt).
6. **[MEDIUM/LOW] readings-400 ohne `no-store`**, `_write_audit` → `logger.exception`, `StarletteHTTPException`-Handler gegen `{detail}`-Leck.
7. **[bekannt] E-43** (Fault-vs-Stale-Diagnose) — bereits accept & defer; kein neuer Handlungsdruck.

*Erstellt vom Architekten-Tiefenaudit-Skill. Befunde sind Fakten + `datei:zeile`; Entscheidung & Fix liegen beim Architekten (Lucas).*
