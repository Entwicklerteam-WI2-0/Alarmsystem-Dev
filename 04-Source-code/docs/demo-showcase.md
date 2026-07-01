# Demo-Feed & Feature-Showcase — `tools/demo/g1_feed.py`

> **Zweck:** Eine reproduzierbare Test-/Präsentationsumgebung mit **zwei Modi**:
> 1. **Live-Sim** — ein „lebendiger" G1-Feed mit realistischen Schwankungen, der die Ampel/
>    Alarme/Grundfunktion beweist (natürliche Werte, kein Flatline-Fail-safe).
> 2. **Feature-Showcase** — fährt in ~10–12 min **alle** Features nacheinander an und prüft
>    jeden Schritt **aktiv gegen die `/v1`-API** (self-checking, `PASS`/`FAIL`).
>
> **Ein Codebase für Windows und Pi** (Variante A): `g1_feed.py` löst das frühere Windows-only
> `Alarmsystem-Demo/feed.ps1` ab. Die reine Ramp-/Dither-/Preset-Logik liegt netzfrei in
> `tools/demo/feed_core.py` und ist in `tests/test_demo_feed.py` gegen die echte
> Vereisungskaskade (`assess_ice_risk`, inkl. Frostpunkt-Referenz E-45) verifiziert.

---

## Warum ein rampender Feed? (löst zwei Betriebsfallen)

| Falle | Ohne Feed | Mit `g1_feed.py` |
|---|---|---|
| **Flatline-Fail-safe** (NF-01, `flatline_epsilon_c=0,15`) | Ein statischer State (z. B. immer `-2,0`) gilt nach 15 min als „eingefrorener Sensor" → `unknown`. | Leichtes Dither (> 0,15 °C) hält den Feed „lebendig". |
| **Sprung-Guard** (`> 5 °C/min` → Reading verworfen) | Manueller Szenariowechsel (GRÜN 15 °C → ROT −2 °C) wird verworfen, Ampel ändert sich nicht → DB leeren + Neustart nötig. | Sanfte Rampen (≤ 1 °C/Tick) fahren die Ampelkaskade **ohne** Reset durch. |

---

## Modus 1 — Live-Sim

Läuft als Teil von `start.ps1` (Windows) bzw. `testrun-sim.sh` (Pi) automatisch mit. Szenario
**live** umschalten über die 1-Wort-Datei `scenario.txt` (der Feed rampt sanft dorthin):

```
green | yellow | orange | red | stale | fault | down
```

**Winter-Auto-Tagesgang** (statt `scenario.txt` manuell zu schalten):

```bash
# aus 04-Source-code/
python -m tools.demo.g1_feed --mode live --profile winter
```

fährt zyklisch `green → yellow → orange → red → orange → yellow` (nächtliche Abkühlung durch
die Kaskade, morgendliche Erholung) mit realistischen Schwankungen.

### Szenario-Presets (Center; gegen `config/thresholds.json` verifiziert)

| Szenario | `surface` / `air` / `humidity` (+Flags) | erwartete Ampel |
|---|---|---|
| **green** | `5,0 / 5,0 / 50` | `green` |
| **yellow** | `0,5 / 1,5 / 88` | `yellow` (T_s ≤ 1 °C) |
| **orange** | `-0,5 / -0,5 / 95` | `orange` (T_s ≤ 0, feucht) |
| **red** | `-2,0 / -1,0 / 98` | `red` + CRITICAL-Alarm |
| **stale** | `age_s=200` | `unknown`, `is_stale=true` |
| **fault** | `status=fault` | `unknown` |
| **down** | `health_down=true` | `unknown` (`/health` 503) |

> **Korrigierte Preset-Bugs (vs. altes `feed.ps1`):** `yellow` war `1,5 °C` (> `gelb_auffang` 1,0 →
> zeigte fälschlich GRÜN), `orange` war `0,5 °C` (> Gefrierpunkt 0,0 → zeigte fälschlich GELB).
> Beide Center sind jetzt gegen `assess_ice_risk` getestet (`tests/test_demo_feed.py`).

---

## Modus 2 — Feature-Showcase (self-checking)

Fährt getaktet durch **alle** Features und prüft jeden Schritt live gegen die API. **Echte
Timings** (Backend-Poll 30 s, Anzeige-Hysterese On-Delay 60 s) → Durchlauf real ~10–12 min.

**Voraussetzung:** Der Stack läuft (Backend + G1-Sim), und **kein Live-Feed schreibt parallel**
in `g1_state.json` (sonst kämpfen zwei Schreiber). Unter Windows erledigt das `showcase.ps1`
(stoppt nur den Feed, lässt Backend + Sim laufen).

```powershell
# Windows: nach start.ps1
& "$env:USERPROFILE\Desktop\Alarmsystem-Demo\showcase.ps1"
```
```bash
# Repo/Pi (aus 04-Source-code/): Live-Feed vorher stoppen
python -m tools.demo.g1_feed --mode showcase
```

### Ablauf & erwartete Ergebnisse

| # | Schritt | Prüft | Erwartet |
|---|---|---|---|
| 1 | `health` | `GET /v1/health` | `200 {status: ok}` |
| 2 | `green` | Ampel treiben | `risk_level=green` |
| 3 | `thresholds` | `GET` + Auth-Gate | GET `200`; POST ohne Key `401`/`503`; POST mit Key `201` |
| 4 | `yellow` | Ampel treiben | `risk_level=yellow` |
| — | `gelb-prognose` | opportunistisch | GELB via 30-min-Prognose (trend-/timing­abhängig, **nie FAIL**) |
| 5 | `orange` + Alarm | Ampel + SSE | `risk_level=orange`; aktiver **WARNING**-Alarm |
| 6 | `red` + Alarm | Ampel + SSE | `risk_level=red`; aktiver **CRITICAL**-Alarm |
| 7 | `ack` / `double-ack` | `POST /v1/alarms/{id}/ack` | `200`; erneuter Ack `409` (NF-09) |
| 8 | `stale` | Fail-safe | `risk_level=unknown`, `is_stale=true` |
| 9 | `fault` | Fail-safe | `risk_level=unknown`, `sensor_status=fault` |
| 10 | `recovery` | unknown → GRÜN | `risk_level=green` (keine klebende Ampel) |
| 11 | `audit` | `GET /v1/audit` | enthält `assessment_made`, `alarm_raised`, `alarm_acknowledged` (+ `reading_ingested`, `sensor_fault`) |
| 12 | `readings` | `GET /v1/readings` | ≥ 1 Eintrag (Historie) |

Am Ende: `ALLE N Schritte PASS` (Exitcode 0) oder eine Liste der `FAIL`-Schritte (Exitcode 1).

> **Auth (Schritt 3):** `start.ps1`/`showcase.ps1` setzen `G2_API_KEY=demo-showcase-key` (lokaler
> Demo-Key, **kein echtes Secret**). Ist kein Key gesetzt, überspringt der Showcase den `201`-Teil
> und prüft nur, dass der Schreibpfad bewacht ist (`401`/`503`).

---

## Bezug

- Feed-Kern + Tests: `tools/demo/feed_core.py`, `tests/test_demo_feed.py` (netzfrei, gegen `assess_ice_risk`).
- Live-Test allgemein: [`live-test-runbook.md`](live-test-runbook.md) · Sim: [`../tools/g1_sim/README.md`](../tools/g1_sim/README.md).
- Kaskade/Schwellen: `src/assessment/core.py`, `config/thresholds.json` (parametrierbar, NF-05).

*Lebendes Dokument — bei Schwellen-/Preset-Änderung `tests/test_demo_feed.py` neu grün ziehen und die Tabellen hier nachführen.*
