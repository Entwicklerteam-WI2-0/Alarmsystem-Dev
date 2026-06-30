# ADR E-44 — G1-Kontextfelder (Oberflächenfeuchte + Wind): Aufnahme (v1.1) + Live-Auslieferung (v1.2)

> **ID:** E-44 · **Status:** Beschlossen + umgesetzt (v1.1 via PR #164, v1.2 via PR #169 — beide in `main`) · **Datum:** 2026-06-29
> **Index:** Kurzeintrag im zentralen Logbuch [`Entscheidungslog-Lucas-Systemarchitektur.md`](Entscheidungslog-Lucas-Systemarchitektur.md) (E-44) verweist hierher.
> **Bezug:** FA-03 · NF-01 · NF-05 · RB-01 · E-31 · E-32 · E-36 · DTB-26 · DTB-35 · PR #164 (v1.1) · PR #169 (v1.2)

## Titel

G1 liefert neu zwei zusätzliche Messgrößen: eine **kalibrierte Oberflächenfeuchte** (`surface_moisture_pct`, %)
und eine **Windgeschwindigkeit** (`wind_speed_ms`, m/s). G2 nimmt beide als **optionale Kontextfelder** auf —
gespeichert und an G3 ausgeliefert, aber **nicht bewertungsrelevant** (kein Faktor der Vereisungskaskade).
Dieser Eintrag dokumentiert die Entscheidung in **zwei additiven Stufen**: **v1.1** (Aufnahme in Ingest,
Persistenz, Historie) und **v1.2** (zusätzliche Auslieferung im Live-Snapshot `assessment/current`).

## Kontext

- Der API-Vertrag v1.0 ist **eingefroren** (DTB-35). Die Aufnahme neuer Felder ist eine bewusste,
  **additive** Contract-Evolution — kein Bugfix, kein Breaking Change.
- Beide Felder sind **kein** Anforderungs-Bestandteil als Bewertungsgröße und es gibt **keine** von G1
  validierte Schwelle dafür. Sie dienen Anzeige/Kontext (Betrieb, Forensik, Frontend).
- G1 bietet je Messgröße mehrere Repräsentationen an (z. B. `wind_speed_ms` / `wind_speed_kmh` / `wind_raw`
  sowie die kalibrierte vs. rohe Oberflächenfeuchte). Die exakten JSON-Keys wurden geprüft/bestätigt.

## Entscheidung

1. **Aufnahme als optionale Kontextfelder** (analog `pressure_hpa`): gespeichert + an G3 ausgeliefert,
   **ohne Einfluss auf `risk_level`/Ampel/Alarme**.
2. **Konsumiert werden nur die kalibrierten/SI-Werte:** `surface_moisture_pct` (%) und `wind_speed_ms` (m/s).
   Die Rohwerte (`surface_moisture_raw`, `wind_speed_kmh`, `wind_raw`) nimmt G2 bewusst **nicht** — Sensor-
   Kalibrierung ist G1-Hoheit; m/s ist SI-konform und passt zur Einheiten-Suffix-Konvention.
3. **v1.1 — Ingest/Persistenz/Historie:** Poller liest beide nicht-blockierend (defekt → `null`, Pflicht-Trias
   nie blockiert), speichert sie (`reading`-Spalten + idempotente Migration) und liefert sie in
   `GET /v1/readings` (`ReadingResponse`). *(Umgesetzt + gemergt via PR #164.)*
4. **v1.2 — Live-Snapshot:** `GET /v1/assessment/current` liefert beide Felder zusätzlich aus dem aktuellen
   Reading, damit G3 sie **neben der Ampel live** anzeigen kann (ohne die Historie zu pollen). Fail-safe
   konsistent: bei `risk_level=unknown` (stale/fault) werden sie **genullt** wie die Messwerte (NF-01).
   *(Umgesetzt + **gemergt via PR #169** in `main` — mit Konfliktauflösung gegen den parallelen Wire-Change #168.)*

## Begründung

- **Nicht bewertungsrelevant:** keine Anforderung, keine validierte Schwelle — eine Aufnahme in die Kaskade
  wäre Scope-Ausweitung ohne Beleg (dieselbe Linie wie der Niederschlag-Scope-Schnitt, E-32). NF-01 unberührt.
- **Sanity ohne Config-Schwelle (NF-05):** Da nicht bewertungsrelevant, ist ein `config/`-Schwellenwert
  unnötig (würde Pflicht-Keys in alle Schwellen-Configs zwingen). Der Ingest prüft Typ/Endlichkeit
  (nicht-blockierend); ein physikalischer Sanity-Deckel ist optional.
- **Live-Auslieferung (v1.2):** Der Frontend-Mehrwert ist der **aktuelle** Wert neben der Ampel; die reine
  Historie (`/v1/readings`) zwänge G3 zum Poll der Historie. `assessment/current` ist der natürliche Ort.
- **Fail-safe-Nullung:** Veraltete/defekte Kontextwerte bei grauer Ampel zu zeigen wäre irreführend → bei
  `unknown` `null`, exakt wie `surface_temp_c`/`dew_point_c`.

## Alternativen (erwogen)

- **Rohwerte konsumieren** (`*_raw`, `wind_speed_kmh`) — *verworfen:* uninterpretiert/redundant; Kalibrierung
  = G1-Hoheit; bricht die Einheiten-Konvention.
- **In die Vereisungsbewertung aufnehmen** — *verworfen:* keine Anforderung/validierte Schwelle; Scope-
  Ausweitung am kritischen Pfad (analog E-32). Bei späterem Bedarf eigene Entscheidung mit G1-Schwelle.
- **Plausibilitäts-Schwelle in `config/thresholds.json`** — *verworfen:* Pflicht-Key-Ripple ohne
  Sicherheitsbezug.
- **Nur Historie, nicht im Live-Snapshot** (= bei v1.1 stehen bleiben) — *verworfen:* G3 müsste für den
  aktuellen Wert die Historie pollen; der Live-Snapshot ist der saubere Ort (→ v1.2).
- **Kontextfelder im Fail-safe-Fall aus dem letzten guten Reading zeigen** (statt nullen) — *verworfen:*
  würde veraltete Werte bei `unknown` suggerieren; inkonsistent mit der Messwert-Nullung (NF-01).

## Konsequenzen

- **Additiv / rückwärtskompatibel:** kein `/v2/`. v1.1 und v1.2 ändern den eingefrorenen Wire-Kern nicht.
- **Abstimmung (DTB-26):** exakte G1-JSON-Keys bestätigt; **G3-Sign-off (Nick)** für v1.2 (Auslieferung im
  Live-Snapshot) einzuholen — versandfertige Nachricht liegt vor.
- **Umsetzung (beide Stufen in `main`):** v1.1 via **PR #164**; v1.2 via **PR #169** (Schema +
  `build_assessment_current` + `openapi.yaml`/`API_FROZEN_v1`, Unit- + Endpoint-Tests, Suite grün) — beide
  gemergt und in `origin/main` verifiziert.
- **Kein neuer Endpoint:** beide Felder reisen auf den bestehenden Nähten mit (G1 `GET /current` → Ingest;
  G2 `GET /v1/readings` + `GET /v1/assessment/current` → G3). `assessment/`/`alarm/`/`forecast/` unberührt.

## Mitwirkung / Zuschreibung

- **v1.1** (Aufnahme der Kontextfelder, Wahl der konsumierten/kalibrierten Felder) wurde im Team umgesetzt
  und über **PR #164** gemergt; die m/s-Wahl für Wind wurde von Lucas + Johannes bestätigt.
- **v1.2** (Auslieferung im Live-Snapshot + Fail-safe-Nullung) ist die Entscheidung/Umsetzung von Johannes
  (Systemarchitekt). Dieser Eintrag fasst beide Stufen nachvollziehbar zusammen — die v1.1-Stufe war zuvor
  ohne Entscheidungslog-Eintrag.

## Bezug & Querverweise

- **FA-03** (Messwert-Historie) · **NF-01** (Fail-safe, unberührt) · **NF-05** (Wind/Feuchte keine Schwelle) ·
  **RB-01** (kein Aktor) · **E-31** (Pull) · **E-32** (Scope-Schnitt-Linie) · **E-36** (flacher Wire-Contract) ·
  **DTB-26** (Seam-Sync) · **DTB-35** (Freeze v1.0) · **PR #164** (v1.1).
