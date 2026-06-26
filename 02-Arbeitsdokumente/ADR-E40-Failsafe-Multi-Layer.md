# ADR E-40 — Fail-safe als Multi-Layer-Architektur (NF-01)

> **ID:** E-40 · **Status:** Akzeptiert · **Datum:** 2026-06-27 · **Task:** DTB-48
> **Autor / DRI:** Lucas Vöhringer (Systemarchitekt, DRI NF-01 — nicht delegierbar)
> **Index:** Kurzeintrag im zentralen Logbuch [`Entscheidungslog-Lucas-Systemarchitektur.md`](Entscheidungslog-Lucas-Systemarchitektur.md) (E-40) verweist auf dieses Dokument.
> **Bezug:** NF-01 · E-34 · E-35 · E-31 · E-36 · DTB-13 · DTB-43 · DTB-64 · blockt DTB-20

## Titel

Fail-safe wird **nicht an einer einzelnen Stelle**, sondern als **mehrschichtige Architektur** garantiert:
jede Schicht erzwingt eigenständig `unknown` (oder mind. ORANGE/GELB, **nie GRÜN**), inklusive DB-Ausfall.

## Kontext

**NF-01 (Fail-safe-Pflicht):** Bei veralteten, fehlenden oder defekten Daten muss das System
`RiskLevel=unknown` liefern und **nie `green`** — als **Default-Verhalten, nicht als Sonderfall**.

Der Fail-safe war im Code bereits über mehrere Schichten verteilt umgesetzt (DTB-13, DTB-28, DTB-38,
DTB-64), aber **nicht als eine zusammenhängende Architektur-Entscheidung dokumentiert**. DTB-48 schließt
diese Lücke: Es benennt explizit, welche Schicht den sicheren Zustand erzwingt — inkl. des in der
ursprünglichen Kaskaden-Entscheidung (E-34) noch nicht behandelten **DB-Ausfall-Falls**.

**ID-Hinweis (Kollision vermieden):** DTB-48 sah ursprünglich „E-39" vor (damals höchste vergebene ID
= E-38). E-39 wurde inzwischen für das Audit-Log (DTB-29) vergeben → dieser ADR erhält die nächste freie
ID **E-40** (analog zu den bereits aufgetretenen Kollisionen E-29/E-32).

## Entscheidung

NF-01 wird als **mehrschichtige Fail-safe-Architektur** garantiert. Jede Schicht, die ihre
Eingangs-Invariante nicht sicherstellen kann, erzwingt selbst den sicheren Zustand;
**GRÜN nur, wenn ALLE Schichten ok sind.** Die Schichten:

| # | Schicht | Auslöser | Erzwingt | Fundstelle |
|---|---------|----------|----------|------------|
| 1 | **Ingest / Aktualität (Stale)** | Reading älter als `stale_timeout_s` (Config) oder fehlend | `unknown` | `is_stale` → `build_unknown_assessment` (`failsafe.py`, DTB-13) |
| 2 | **Sensor-Status (Fault)** | `reading.status = fault` | `unknown` | `AssessmentService` (`service.py`, DTB-64) |
| 3 | **Datenqualität / Plausibilität** | Sprung / Flatline / Zeitstempelfehler | `unknown` | `check_plausibility` (`failsafe.py`, `Schwellenwerte.md §3`) |
| 4 | **Storage / DB-Ausfall** | PyMySQL-Fehler (`OperationalError` / Verbindungsabbruch / Config) | `RepositoryError` → **HTTP 503** `Error{code,message}` / `unknown` | `repository.py`, `assessment_repository.py`, `main.py` (DTB-43) |
| 5 | **Assessment-Kaskade** | `ΔT` nicht berechenbar (`T_d` fehlt, `RH`/`T_a` defekt) | **Feuchte = wahr** ⇒ bei `T_s ≤ 0` mind. ORANGE, sonst GELB, **nie GRÜN** | `assess_ice_risk` (DTB-38, **E-34**) |
| 6 | **Serve-Zeit-Re-Check** | Reading beim Abruf inzwischen stale/fault | `unknown` + Messwerte genullt | `build_assessment_current` (`service.py`, DTB-43/DTB-64) |

**Abgrenzung (wichtig):** Schichten 1–4 und 6 liefern `unknown`. **Schicht 5 (Kaskade) liefert
ORANGE/GELB**, nicht `unknown` — ein konservativer Bewertungs-Fallback nach E-34, der ebenfalls
**nie GRÜN** ergibt, aber innerhalb der regulären Ampel bleibt.

## Begründung

Eine einzige Prüfstelle ist fragil — sie deckt nicht ab, dass die Bewertung gut sein kann, während die
DB weg ist, oder dass ein gespeicherter Wert zwischen Bewertung und Abruf altert. **Defense-in-depth:**
jede Schicht hat ihren eigenen Fail-safe-Pfad, der sichere Zustand ist strukturell der Default.

- **Erreichbarkeit getrennt von Datenaktualität:** DB-Fehler/`/health` und Stale (`measured_at`) sind
  **zwei unabhängige `unknown`-Pfade** (E-31: Pull, `/health` getrennt vom Mess-Zeitstempel).
- **DB-Ausfall als 503 + `unknown`, nicht als 500/Crash:** ein Crash ist kein definierter sicherer
  Zustand; ein expliziter 503 mit Contract-Fehlerformat ist es (E-35/E-36).
- **`unknown` ist ein eigener Zustand, nicht GELB:** GELB ist eine reguläre Bewertungsstufe der Kaskade;
  der Fail-safe braucht einen eigenen Zustand, sonst ist „echte Bewertung" nicht von „keine verlässliche
  Bewertung" unterscheidbar.

## Alternativen (verworfen)

- **Fail-safe nur in der Bewertungslogik (E-34 allein):** deckt DB-Ausfall und das Altern zur Serve-Zeit
  nicht ab → NF-01 wäre lückenhaft.
- **DB-Ausfall als 500 / unbehandelte Exception:** kein definierter sicherer Zustand; 503 + `unknown`
  ist explizit und fail-safe (E-35).
- **Stale nur zur Bewertungszeit prüfen:** die gespeicherte Bewertung altert; ohne Serve-Zeit-Re-Check
  könnte ein veralteter GRÜN-Wert ausgeliefert werden.
- **GELB statt `unknown` als sicherer Zustand:** macht „echte Bewertung" von „keine Bewertung"
  ununterscheidbar; Fail-safe braucht einen eigenen Zustand.

## Konsequenzen

- **Code bereits vorhanden** (dieser ADR dokumentiert, implementiert nicht): `src/assessment/failsafe.py`
  (Stale/Plausibilität/`build_unknown_assessment`), `src/storage/repository.py` +
  `assessment_repository.py` (`RepositoryError`), `src/assessment/service.py` (Assess-Zeit-NF-01),
  `src/main.py` (DTB-43 503-Pfad + Serve-Zeit-Re-Check).
- **Offen / empfohlen:** ein Fail-safe-**Integrationstest** je Schicht (DB-Ausfall → 503/`unknown`,
  Stale → `unknown`) als eigener Test-Task (z. B. unter DTB-49) — nicht Scope von DTB-48 (Doku).
- **Reihenfolge:** DoD verlangte DTB-48 vor DTB-13/DTB-20. DTB-13 ist bereits „Erledigt" (überholt);
  für DTB-20 (P3.2, noch offen) ist der ADR rechtzeitig.

## Bezug & Querverweise

- **NF-01** (Fail-safe-Pflicht) · **E-34** (priorisierte Kaskade, Assessment-Schicht) ·
  **E-35** (DB-Ausfall-Schicht, rohes PyMySQL) · **E-31** (`/health` getrennt von Datenaktualität) ·
  **E-36** (eingefrorener G2→G3-Contract: `unknown`+`is_stale=true` als Fail-safe-Signal / API-Format).
- Tasks: **DTB-13** (Stale/Plausibilität), **DTB-43** (503-Pfad), **DTB-64** (Assess-/Serve-Zeit-Verdrahtung);
  **blockt DTB-20** (P3.2).
- Persönliches Log: DTB-64-Eintrag (2026-06-26).
