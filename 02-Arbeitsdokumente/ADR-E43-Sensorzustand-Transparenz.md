# ADR E-43 — Sensorzustands-Transparenz am Serve-Layer (Fault vs. Stale vs. keine Daten)

> **ID:** E-43 · **Status:** Beschlossen — bewusst akzeptiert, Umsetzung nach M3 (*accept & defer*) · **Datum:** 2026-06-28
> **Autor:** Johannes Petzold (Systemarchitekt) · **Mitentscheid / DRI:** Lucas Vöhringer (NF-01-Naht)
> **Index:** Kurzeintrag im zentralen Logbuch [`Entscheidungslog-Lucas-Systemarchitektur.md`](Entscheidungslog-Lucas-Systemarchitektur.md) (E-43) verweist auf dieses Dokument.
> **Bezug:** NF-01 · RB-01 · FA-04 · R1–R5 · E-31 · E-36 · E-40 (Schichten 1/2/6) · E-42 · DTB-43 · DTB-49 · DTB-64
> **Empirische Basis:** lokaler Live-Verify 2026-06-28 (G1-Simulator, 6 Szenarien Ende-zu-Ende).

## Titel

Ein defekter Sensor (`status=fault`) und ein stiller/veralteter Sensor (Stale, keine Daten) sind am
ausgelieferten Wire-Response **derzeit nicht unterscheidbar** — beide erscheinen als `risk_level=unknown`
mit `sensor_status=ok` und `is_stale=false`. Diese Diagnose-Lücke wird **erkannt, bewusst akzeptiert und
nach M3 behoben** — nicht stillschweigend gefüllt und nicht kurz vor der Demo am kritischen Pfad umgebaut.

## Kontext

Beim lokalen Live-Verify (G1-Simulator, scharfer Bewertungszyklus) zeigten sich zwei Beobachtungen:

1. **Stale-Fall:** Bei veralteten Daten liefert das System korrekt `risk_level=unknown` (nie GRÜN), aber
   das Wire-Feld **`is_stale` bleibt `false`** für ein Fenster von bis zu `stale_timeout_s` (120 s).
2. **Fault-Fall:** Meldet G1 `status=fault`, liefert das System ebenfalls `unknown` (nie GRÜN), aber mit
   **`sensor_status=ok`** und `driving_factor=stale` — ein **gemeldeter Sensordefekt ist am Endpoint nicht
   von „Sensor still / keine Daten" unterscheidbar**.

**Gemeinsame Wurzel:** Der Ingest-Poller fasst *alle* Fehlerzustände — Fault, Stale, G1 nicht erreichbar —
in ein einziges `None` zusammen und verwirft das Reading (`poller.py`, `_build_reading`). Der *Grund* geht
dabei verloren; die nachgelagerte Bewertung baut generisch „keine aktuellen Daten" (`driving_factor=stale`),
und der Serve-Pfad (`build_assessment_current`) bewertet `is_stale`/`sensor_status` aus dem **zuletzt
gespeicherten guten** Reading. `build_assessment_current` ist dabei **bereits korrekt** — bekäme es ein
wahrheitsgemäßes Reading, setzte es `sensor_status=fault` / `is_stale=true` selbst. Die Lücke liegt
ausschließlich darin, dass der Sensorzustand den Serve-Layer **nicht erreicht**.

**Wichtig:** Dieses Verwerfen ist eine **bewusste, getestete Designlinie**, kein Versehen — der
Integrationstest `test_schicht2a` (DTB-49) prüft ausdrücklich, dass ein Fault-Snapshot verworfen wird und
**nichts persistiert** wird. Der Verwurf schützt zugleich die Sprung-/Flatline-Vergleichsbasis vor
Vergiftung (E-42). Eine Änderung überstimmt also eine dokumentierte Entscheidung.

## Entscheidung

Für **M3 keine Code-Änderung**: Das aktuelle Verhalten (Fault/Stale/Ausfall → `unknown`, nie GRÜN) bleibt
und ist **sicherheitstechnisch vollständig** (NF-01 in allen Fällen gewahrt — beim Live-Verify in allen 6
Szenarien bestätigt). Die **Diagnose-Verbesserung** (Fault vs. Stale am Wire unterscheidbar machen) wird
als Folge-Task **nach M3** umgesetzt, mit der unten empfohlenen, eingriffsarmen Variante.

## Begründung

- **Sicherheit ist nicht betroffen.** „Nie GRÜN bei Fault/Stale/Ausfall" hält bereits in allen Fällen; der
  Fix verbessert **Beobachtbarkeit/Diagnostik**, nicht den sicheren Zustand.
- **Kein aktueller Konsument.** G3 wertet laut Naht-Abstimmung `risk_level=unknown` aus (nicht
  `sensor_status`/`is_stale`); den menschlichen Kontext liefert bereits das `explanation`-Feld.
- **Der Befund ist trotzdem real und wichtig.** Operativ unterscheidet sich die Korrekturhandlung:
  „Sensor **defekt**" → Techniker / Austausch (Briefing: Vorfeld-Sensoren werden beschädigt; R1/R3),
  „Sensor **still**" → Verbindung/Strom prüfen (R2/R4). Diagnostik genau dafür ist sinnvoll.
- **Timing/Risiko.** Ein Umbau überstimmt eine getestete Designlinie auf dem **kritischen Pfad** (Ingest↔
  Serve-Naht), erfordert das Umschreiben von `test_schicht2a` und ändert die `/v1/readings`-Historie →
  **Regressionsrisiko unmittelbar vor der M3-Demo** für einen Nutzen, den vor der Demo niemand konsumiert.
  **Wichtig ≠ dringend:** richtig nach der Demo umsetzen statt vorher hetzen.

## Alternativen (erwogen)

- **A) Sofort vor M3 umsetzen** — *verworfen:* Regressionsrisiko am kritischen Pfad kurz vor der Demo, kein
  aktueller Konsument, sicherheitsneutral.
- **B) Fault/Stale-Readings persistieren** (statt verwerfen) → `build_assessment_current` spielt
  `sensor_status`/`is_stale` automatisch korrekt aus. *Mächtig, aber teuer:* ändert die
  `/v1/readings`-Historie, braucht einen ausdrücklichen Schutz der Sprung-/Flatline-Basis (E-42) und kehrt
  `test_schicht2a` um. **Nur** wählen, wenn die volle Reading-Historie der Defekt-/Stale-Zustände gebraucht wird.
- **C) Nur den verlorenen Grund durchreichen** (Fault / Stale / Ausfall) und in `explanation`/
  `driving_factor` des `unknown`-Assessments schreiben — **ohne** Datenmodell-Änderung, **ohne**
  Baseline-Risiko, **ohne** `/v1/readings`-Semantikänderung. Holt den Großteil des operativen Werts
  (Operator/G3 sehen „Sensor defekt" im Klartext) bei minimalem Eingriff. **→ empfohlen für die spätere Umsetzung.**
- **D) Nicht dokumentieren / stillschweigend lassen** — *verworfen:* echter Befund, gehört nachvollziehbar festgehalten.

## Konsequenzen

- **M3:** keine Code-Änderung; aktuelles, sicheres Verhalten bleibt. G3-Hinweis unverändert: auf
  `risk_level=unknown` triggern; `explanation` gibt groben Kontext.
- **Contract-Abweichung bewusst akzeptiert:** der eingefrorene Contract (E-36) nennt `is_stale=true` als
  Stale-Fail-safe-Signal; die aktuelle Abweichung (`is_stale=false` für ≤ `stale_timeout_s`) ist akzeptiert,
  weil `risk_level=unknown` das maßgebliche und korrekte Signal bleibt. Bei der Umsetzung (Option C) wird die Abweichung mitbehoben.
- **Offen / Folge-Task (noch ohne DTB-ID):** Option C nach M3; bei Umsetzung je ein benannter Test für
  beide Beobachtungen (Fault unterscheidbar; `is_stale` ohne Lag) plus Beibehaltung des Baseline-Schutzes (E-42).

## Bezug & Querverweise

- **NF-01** (Fail-safe, in allen Fällen gewahrt) · **FA-04** (Sensor-Defekt/Stale-Erkennung) ·
  **R1–R5** (falsche Sensordaten, Kommunikations-/Stromausfall, Wartbarkeit) · **RB-01** (kein Aktor, unberührt).
- **E-31** (`/health` getrennt von Datenaktualität) · **E-36** (Wire-Contract, `unknown`+`is_stale`) ·
  **E-40** (Multi-Layer-Fail-safe, Schichten 1/2/6) · **E-42** (Sprung-/Flatline-Basis, Vergiftungsschutz).
- Tasks: **DTB-43** (Serve-Pfad), **DTB-49** (Fail-safe-Integrationstests, `test_schicht2a`), **DTB-64** (Verdrahtung).
