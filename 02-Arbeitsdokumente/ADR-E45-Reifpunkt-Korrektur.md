# ADR E-45 — Konservative Reifpunkt-Referenz unter 0 °C (umgesetzt)

> **ID:** E-45 *(vorgeschlagen — finale Nummer + Index-Zeile im zentralen Logbuch durch Lucas; dort besteht aktuell eine E-44-Doppelvergabe, die separat aufzulösen ist)* · **Status:** **Beschlossen + UMGESETZT** (in `main`, Code-PR gemergt) · **Datum:** 2026-07-01
> **Autor:** Johannes Petzold (Systemarchitekt) · **Mitentscheid / DRI:** Lucas Vöhringer (Naht/E-ID)
> **Bezug:** NF-01 · K1 · FA (Vereisungsbewertung) · E-32 · E-33 · E-34 · DTB-32 · DTB-38 · DTB-69
> **Auslöser:** externes fachliches Gegen-Review (2026-06-30/07-01) — physikalischer Einwand „warum Taupunkt und nicht Reifpunkt unter null?", unabhängig nachgerechnet und bestätigt.

## Titel

Die Vereisungsbewertung rechnete den Feuchte-Abstand `ΔT = T_s − T_d` mit dem **Wasser-Taupunkt** `T_d`
(Magnus über flüssigem Wasser). Für reine **Reif**-Deposition unter 0 °C ist physikalisch der **Reifpunkt**
`T_f` (Sättigung über Eis) maßgeblich. Die Kaskade nutzt jetzt unter dem Gefrierpunkt die **konservativere
Referenz `max(T_d, T_f)`** — die Korrektur ist umgesetzt, getestet und in `main`.

## Kontext

Unter 0 °C liegt der Reifpunkt über dem Wasser-Taupunkt (`T_f > T_d`), weil die Sättigungsdampfdruckkurve
über Eis unter der über unterkühltem Wasser liegt. Der reale Reif-Abstand `ΔT_frost = T_s − T_f` ist damit
**kleiner** als das berechnete `T_s − T_d` — der Wasser-Taupunkt **unterschätzte** das Reifrisiko unter null.

**Unabhängig nachgerechnet** (Eis-Magnus a=22,46 / b=272,62 gegen Wasser-Magnus), Offset `T_f − T_d`:

| Bahn-Temperatur | Offset |
|---|---|
| ≈ 0 °C | ~0 K |
| −5 °C | ~0,65 K |
| −10 °C | ~1,25 K |

**Der reale Effekt:** Weil ROT `ΔT ≤ 0` verlangt, feuerte ROT via ΔT faktisch nur für flüssige
Kondensation/Glatteis, nicht für reinen Reif. Und unterhalb ≈ −8 °C wuchs der Offset über 1,0 K, sodass
*marginal einsetzender* Reif rechnerisch auf **GELB** (kein Alarm) statt ORANGE fiel — ein systematischer
Under-Alarm in der **unsicheren** Richtung, ausgerechnet im Kernszenario „Reif auf Runway".

**Randbedingung (PROJEKTFINAL, 2026-07-01):** Messtechnisch validierte G1-Schwellen sind **nicht mehr zu
erwarten** (ein Sensor defekt, Feldkalibrierung im Studierenden-Team nicht möglich). Eine spätere Kalibrierung
gegen G1-Frostdaten als Lösungsweg entfällt damit — die Entscheidung muss **jetzt und autonom** fallen.

## Entscheidung

Die Kaskade (`assess_ice_risk`) verwendet bei `T_s ≤ t_s_gefrierpunkt_c` die Feuchte-Referenz
**`max(T_d, T_f)`** statt allein `T_d` (`T_f` aus `frost_point_from_dew_point`, geschlossene Inversion der
Eiskurve aus dem Taupunkt). Oberhalb des Gefrierpunkts bleibt der Wasser-Taupunkt die Referenz.

## Begründung

- **Strikt einseitig (der entscheidende Punkt).** `max(T_d, T_f) ≥ T_d` ⇒ die abgeleitete ΔT wird **nie
  größer** als vorher ⇒ die Klassifikation kann sich nur **anheben**, nie senken. Der Fix kann **keinen neuen
  Miss und kein neues GRÜN** erzeugen — beweisbar sicher. Preis: etwas mehr Fehlalarme bei sehr kalten,
  feuchtnahen Lagen — laut K1 („lieber zehn Fehlalarme als ein vereistes Flugzeug") **gewollt**.
- **„Warten" ist keine Option mehr.** Da keine G1-Validierung mehr kommt (PROJEKTFINAL), wäre ein bekannter
  Bias in die unsichere Richtung auszuliefern nicht vertretbar, wenn der Fix einseitig-sicher und billig ist.
- **Klareis bleibt korrekt.** Der Reifpunkt triggert *früher* (bei wärmerer Oberfläche) als der Wasser-Taupunkt;
  er unterversorgt gefrierenden Regen/Klareis also nicht, sondern deckt beide Regime konservativ ab.
- **Vorfall-Validierung geschützt.** Beide dokumentierten Vorfälle bleiben unverändert grün (Vorfall 1 trockene
  Kälte → GELB, kein Fehlalarm zurück; Vorfall 2 → ROT).
- **Contract unangetastet.** Die Wire-Felder `dew_point_c` und `delta_t` bleiben der echte
  Wasser-Taupunkt bzw. `T_s − T_d` (eingefrorener Contract); nur Klassifikation und Erklärtext werden
  konservativ. Kein `/v2`.

## Alternativen (erwogen)

- **A) Wasser-Taupunkt behalten + nur dokumentieren (accept & document)** — *verworfen:* solange G1-Werte
  ausstanden, war das vertretbar; nachdem sie **endgültig ausfallen** (PROJEKTFINAL) und der Fix einseitig-
  sicher ist, ist das Belassen eines unsicheren Bias die schwächere Wahl.
- **B) Reifpunkt konservativ implementieren (`max(T_d, T_f)` unter 0 °C)** — **gewählt.**
- **C) ORANGE-/ROT-Schwellen pauschal anheben** — *verworfen:* verschlechtert die Fehlalarmrate ohne physika-
  lische Basis, vermischt Modell- mit Schwellenkalibrierung.
- **D) Reifpunkt für ALLE T_s (auch > 0 °C)** — *verworfen:* über 0 °C gibt es keine Reif-Deposition; dort ist
  der Wasser-Taupunkt (Klareis/gefrierender Regen) die richtige Kurve.

## Konsequenzen

- **Verhalten:** Reif-Beginn unter ≈ −8 °C jetzt **ORANGE** (Alarm) statt GELB; aktive Reif-Deposition am/unter
  dem Reifpunkt **ROT**. Trockene Kälte bleibt GELB (kein Fehlalarm). Wire-Response unverändert.
- **Umsetzung (in `main`):** neue reine `frost_point_from_dew_point` (`utils.py`) + `_humidity_reference_c`
  (`core.py`); Erklärtext nutzt dieselbe effektive ΔT. TDD (RED→GREEN); **866 Tests grün**, `core.py`+`utils.py`
  **100 %** Coverage, ruff clean. Ein Deadband-Hysterese-Test gegen die frost-korrigierte ΔT neu hergeleitet.
- **Selbst-Review-Fund (WP5):** NaN-Taupunkt hätte im Erklärtext-Pfad `frost_point_from_dew_point(NaN)` und
  damit einen Crash ausgelöst → `isfinite`-Guard + Regressionstest ergänzt.
- **Micro (mitgenommen):** `flatline_epsilon_c = 0,15` war als „2×LSB" beschriftet; korrekt ist `~2,4×LSB`
  (2×LSB = 0,125). Label in `config/thresholds.json` präzisiert; die gleiche Formulierung im persönlichen
  `Ganter-Entscheidungslog` (DTB-20) korrigiert der Autor selbst.

## Bezug & Querverweise

- **NF-01** (Fail-safe, gewahrt — nie GRÜN) · **K1** (FN ↔ FP, Sicherheits-Bias, hier bewusst Richtung
  Over-Alarm) · **E-32/E-33/E-34** (3-Faktor-Modell, Feuchte-Definition, Kaskade) · **DTB-32** (Taupunkt-
  Rechner) · **DTB-38** (Bewertungskaskade) · **DTB-69** (ursprünglich Schwellen-Tuning mit G1; durch die
  autonome Umsetzung + PROJEKTFINAL erledigt/gegenstandslos, Rest = 2-Jahres-Ausblick).
