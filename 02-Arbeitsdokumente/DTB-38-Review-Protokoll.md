# Review-Protokoll DTB-38

## Zusammenfassung

- **Gesamturteil:** REQUEST CHANGES → nachgebessert → **APPROVE** (Stand `716963b`)
- **Commit/Stand:**
  - Ursprüngliches Review: `03ebde5d983f88b32208e38b3552aa58aa61bc7d` auf Branch `feat/dtb-38-assessment`
  - Nachgebessert: `716963b` auf Branch `feat/dtb-38-assessment`
- **Reviewer:** KI-Subagent
- **Review-Datum:** 2026-06-25
- **Nachbesserung durch:** Kimi Code Agent

## Geprüfte Dateien

| Datei | Zweck |
|---|---|
| `04-Source-code/src/assessment/core.py` | Kern-Logik `assess_ice_risk` |
| `04-Source-code/src/assessment/__init__.py` | Öffentlicher Modul-Export |
| `04-Source-code/tests/test_assessment.py` | Unit-Tests für Bewertungslogik |
| `04-Source-code/src/config/loader.py` | Config-Loader / `Thresholds`-Dataclass |
| `04-Source-code/config/thresholds.json` | Schwellenwerte-Datei |
| `04-Source-code/src/model/enums.py` | `RiskLevel`-Enum |
| `02-Arbeitsdokumente/Schwellenwerte.md` §2 | Spezifikation der Kaskade |
| Jira DTB-38 (archidox-devs.atlassian.net) | Ticket-Beschreibung & DoD |

## Befunde nach Kategorie

### Korrektheit

- **Kaskaden-Reihenfolge ROT → ORANGE → GELB → GRÜN ist korrekt implementiert.** Die `if/elif/else`-Kette prüft in genau dieser Priorität und bricht mit der ersten zutreffenden Stufe ab.
- **Schwellenwerte stimmen mit `Schwellenwerte.md` §2 und `config/thresholds.json` überein:**
  - `t_s_gefrierpunkt_c = 0.0`
  - `t_s_gelb_auffang_c = 1.0`
  - `delta_t_kondensation_k = 0.0`
  - `delta_t_feucht_k = 1.0`
  - Prognose-Grenze `t_s_grenz_c = 0.0`
- **Keine Hardcodes:** Alle Entscheidungsgrenzen werden über `thresholds.vereisung` / `thresholds.prognose` bezogen.
- **Vorfall 1 (−2,1 °C Luft, trockene Oberfläche):** Wird korrekt als `GELB` aufgelöst (`T_s = −2.1`, `T_d = −10.0` → ΔT = 7.9 > 1.0 → kein ORANGE/ROT). Der frühere `RH ≥ 90 %`-Term ist nicht mehr vorhanden.
- **Vorfall 2 (+1,2 °C Luft, Oberfläche < 0 °C, feucht):** Wird korrekt als `ORANGE` oder `RED` erkannt (Test prüft `in (ORANGE, RED)`).
- **Fail-safe bei fehlendem Taupunkt:** Wenn `dew_point_c is None` gilt `humid = True`; bei `T_s ≤ 0 °C` wird `ORANGE` (mindestens), bei `T_s > 0 °C` wird `GELB`. `GRÜN` wird in diesem Pfad nie erreicht.
- **Fail-safe bei ungültiger Oberflächentemperatur (NaN):** 🔴 **BLOCKER** — siehe Sicherheits-Kategorie.

### Code-Qualität

- **Lesbarkeit & Naming:** Gut. Funktions- und Variablennamen sind auf Deutsch und sprechend (`surface_temp_c`, `dew_point_c`, `forecast_surface_temp_c`, `delta_t`, `humid`).
- **Funktionsgröße:** `assess_ice_risk` ist mit 21 Statements angemessen klein und fokussiert.
- **Type Hints:** Vollständig (`float | None`, `Thresholds`, `RiskLevel`).
- **Docstrings:** Vorhanden und beschreiben Zweck, Args, Returns und Fail-safe-Verhalten.
- **Keine redundanten Logiken:** Die Feuchte-Berechnung erfolgt an einer Stelle; die Kaskade ist linear.
- **NIT:** Der Kommentar in Zeile 15 („Die Funktion selbst liefert kein `unknown` …") steht leicht im Widerspruch zum Ticket-Text („Stale-Daten oder Sensorausfall → Ausgabe `unknown`"). Für diese reine Funktion ist die Aufteilung nachvollziehbar, aber im Docstring sollte klarer stehen, **welche** ungültigen Eingaben der Aufrufer vorher abfangen muss (z. B. NaN, Stale, fehlendes Reading).

### Tests

- **Alle 12 Tests laufen grün.**
- **Coverage:** 100 % auf `src/assessment/__init__.py` und `src/assessment/core.py` (23 Statements, 0 Miss).
- **Abdeckung:**
  - Kaskade ROT/ORANGE/GELB/GRÜN: abgedeckt.
  - Beide dokumentierte Vorfälle: abgedeckt.
  - Fail-safe bei fehlendem `T_d`: abgedeckt (gefroren → ORANGE, warm → GELB, mit Prognose → GELB).
- **Testnamen:** Verständlich und auf Deutsch; sprechende Namen gemäß Konvention.
- **NIT:** Es fehlen Tests für Grenzwerte und ungültige Zahlen:
  - Exakte Grenzwerte (`T_s = 0.0`, `T_s = 1.0`, `ΔT = 0.0`, `ΔT = 1.0`).
  - NaN/inf-Eingaben (siehe Sicherheits-BLOCKER).
  - `None` als `surface_temp_c` (sollte durch Typisierung ausgeschlossen sein, aber ein Verhaltens-Test wäre sicherheitshalber sinnvoll).

### Lint/Format

- `ruff check src/assessment tests/test_assessment.py` — ✅ sauber
- `ruff format --check src/assessment tests/test_assessment.py` — ✅ sauber

### Sicherheit / Fail-safe

- 🔴 **BLOCKER — NaN-Oberflächentemperatur kann GRÜN ergeben:**
  - `assess_ice_risk(float('nan'), 0.0, thresholds)` → `RiskLevel.GREEN`
  - Ursache: `math.nan <= x` ist immer `False`; die Kaskade greift nicht, und weil `dew_point_c` bekannt ist, wird am Ende `GREEN` zurückgegeben.
  - Risiko: In einem sicherheitskritischen System führt ein ungültiger Sensorwert (NaN) zur niedrigsten Risikostufe. Das verstößt gegen NF-01 („Fehlende/veraltete Daten führen nie zu GRÜN") und das Sicherheits-Bias.
  - Empfohlene Lösung: Eingabevalidierung für `surface_temp_c` (und ggf. `dew_point_c`/`forecast_surface_temp_c`) auf `math.isnan` / `math.isinf`; bei ungültigen Werten entweder `RiskLevel.UNKNOWN` zurückgeben oder eine Exception werfen, die der Aufrufer als `UNKNOWN` behandelt. Da `assess_ice_risk` selbst `UNKNOWN` nicht zurückgibt, sollte dies entweder geändert oder der Aufrufer verpflichtend vorvalidieren.

- **Fail-safe bei fehlendem Taupunkt:** Korrekt konservativ (`ORANGE` bei `T_s ≤ 0 °C`, sonst `YELLOW`, nie `GREEN`).
- **Fail-safe bei `-inf`:** Konservativ (`ORANGE` bei fehlendem `T_d`).
- **Fail-safe bei `+inf`:** Korrekt (`GREEN`).
- **Fail-safe bei `None` für `surface_temp_c`:** TypeError an `surface_temp_c <= …` — akzeptabel, da Typ-Hinweis `float` dies ausschließt; idealerweise aber explizit abgefangen oder dokumentiert.

## Empfohlene Änderungen

1. **BLOCKER — NaN/inf-Validierung einführen.** Beispielhafte Option:
   ```python
   import math
   # am Anfang von assess_ice_risk
   if math.isnan(surface_temp_c) or math.isinf(surface_temp_c):
       return RiskLevel.UNKNOWN  # oder ValueError
   if dew_point_c is not None and (math.isnan(dew_point_c) or math.isinf(dew_point_c)):
       dew_point_c = None  # ungültiger Taupunkt -> konservativ unbestimmt
   if forecast_surface_temp_c is not None and (math.isnan(forecast_surface_temp_c) or math.isinf(forecast_surface_temp_c)):
       forecast_surface_temp_c = None
   ```
   Sollte `assess_ice_risk` weiterhin kein `UNKNOWN` zurückgeben, **muss** der Aufrufer diese Validierung zwingend vornehmen; dann gehört das in die Modul-Doku und in die Aufrufer-Tests (z. B. Poller).

2. **NIT — Docstring präzisieren:** Klar dokumentieren, dass `surface_temp_c` eine gültige endliche `float` sein muss und welche ungültigen Eingaben vom Aufrufer abgefangen werden müssen (NaN, inf, Stale, fehlendes Reading).

3. **NIT — Testabdeckung erweitern:** Tests für exakte Grenzwerte (`T_s = 0.0`, `T_s = 1.0`, `ΔT = 0.0`, `ΔT = 1.0`) und für NaN/inf hinzufügen, sobald das Verhalten festgelegt ist.

## Nachbesserung (durchgeführt auf `716963b`)

1. **BLOCKER behoben:** Eingabevalidierung mit `math.isfinite` eingeführt.
   - `surface_temp_c` nicht endlich → `RiskLevel.UNKNOWN`
   - `dew_point_c` nicht endlich → `RiskLevel.UNKNOWN`
   - `forecast_surface_temp_c` nicht endlich → wird ignoriert (Fail-safe, da optional)
2. **Docstring angepasst:** Funktion darf nun `UNKNOWN` zurückgeben; ungültige Eingaben dokumentiert.
3. **Tests erweitert:**
   - Grenzwert-Tests (`T_s = 0.0`, `T_s = 1.0`, `ΔT = 0.0`, `ΔT = 1.0`)
   - NaN/inf-Tests für `surface_temp_c`, `dew_point_c` und `forecast_surface_temp_c`
4. **Verifikation nach Nachbesserung:**
   - `pytest tests/test_assessment.py`: **21 passed**
   - Coverage `src.assessment`: **100 %**
   - `ruff check` + `ruff format --check`: sauber
   - Gesamtsuite: **83 passed**, 100 % Coverage über `src/`

## Offene Punkte / Rückfragen

- Wie werden ungültige Sensorwerte (NaN, Out-of-Range) aus G1 aktuell im Ingest/Poller behandelt? Falls dort bereits gefiltert wird, reduziert sich das Risiko, aber die Bewertungsfunktion weist sie jetzt selbst als `UNKNOWN` zurück.
