# Persönliches Entscheidungslog — Luca Ganter (G2)
> **Erstellt am:** 2026-06-23 · **Letzte Bearbeitung:** 2026-06-24 · **Zeitraum:** 2026-06-23 bis 2026-06-24
> **Autor:** Luca Ganter · **Status:** laufend gepflegt
> Eigene technische Entscheidungen + Begründung. **Bewertungsrelevant** (Nachvollziehbarkeit, 40 % Einzelleistung).

---

## 2026-06-23 — Konsumierten G1-Vertrag in eigene OpenAPI-Datei trennen
- **Kontext/Task:** DTB-19 (P1.2, OpenAPI v1) · FA-09/FA-01/FA-03 · Naht G1 → G2 → G3. Die DoD verlangt,
  auch den von G2 konsumierten G1-Vertrag (`GET /current`, `GET /health`) zu dokumentieren.
- **Entscheidung:** Den G1-Vertrag in eine **separate** Datei `g1-consumed.openapi.yaml` legen, getrennt von
  der eigenen G2-API-Spec `openapi.yaml` (beide unter `04-Source-code/docs/api/v1/`).
- **Begründung:** G2 hat in der Naht **zwei völlig verschiedene Rollen**: Gegenüber G3 sind wir der
  **Anbieter (Server)**, gegenüber G1 nur der **Abrufer (Client)**. Eine OpenAPI-Datei beschreibt aber
  immer genau **eine** API mit **einem** Server. Hätte ich G1s `/current` mit in unsere `openapi.yaml`
  gepackt, würde die Spec G1s Endpoint fälschlich als unseren eigenen ausweisen — mit falschem Server und
  ohne unser `/v1`-Präfix. Das hätte G3 (und uns selbst beim Implementieren) in die Irre geführt. Mit zwei
  Dateien bleibt jede für sich gültig und die Rollen sind eindeutig: `openapi.yaml` = was wir **anbieten**,
  `g1-consumed.openapi.yaml` = was wir **konsumieren**. Zusätzlich ist der Vertrag so leichter prüfbar (jede
  Datei einzeln validierbar) und beim späteren Einfrieren bleibt eindeutig, wer welchen Endpoint besitzt.
- **Alternativen:**
  - **G1 in dieselbe `openapi.yaml` mischen** — verworfen: erzeugt Rollen-Verwechslung und semantisch
    falsche Server-/Pfad-Angaben.
  - **G1 nur in Prosa/Markdown dokumentieren** (statt OpenAPI) — verworfen: weniger maschinenlesbar/prüfbar;
    eine echte Spec lässt sich validieren und von G2s Poller als Referenz nutzen.
  - **G1 gar nicht dokumentieren** — verworfen: verstößt gegen die Architekten-Vorlage (DTB-19, Punkt 6).
- **Ergebnis/Status:** umgesetzt. Beide Dateien mit `openapi-spec-validator` geprüft; das santa-loop-Review
  bestätigte die Rollen-Trennung G1/G2 ausdrücklich als sauber.

## 2026-06-23 — Double-Ack: `409 Conflict` statt idempotent
- **Kontext/Task:** DTB-19 (P1.2) · PR #48 Review-Finding [MEDIUM] · NF-09 (Audit/Nachvollziehbarkeit) · RB-01.
  Offen war: Was passiert bei `POST /v1/alarms/{id}/ack`, wenn der Alarm schon quittiert ist?
- **Entscheidung:** Erneute Quittierung eines bereits `acknowledged`/`cleared` Alarms wird mit **`409
  Conflict`** abgelehnt — die Operation ist **nicht idempotent**. (Alternative wäre gewesen, ein zweites Ack
  still als `200` durchzulassen.)
- **Begründung:** NF-09 verlangt ein nachvollziehbares Audit-Log. Würde ein zweites Ack lautlos als `200`
  akzeptiert, gäbe es keinen klaren Hinweis auf das versehentliche Doppel-Quittieren, und es bliebe unscharf,
  welche Quittierung „zählt". Mit `409` lehnt das System die Doppel-Quittierung **explizit** ab: der
  Alarm-Zustand bleibt eindeutig und jede gültige Quittierung ist genau **ein** Audit-Eintrag. Das `409`
  signalisiert dem Frontend zudem klar „Zustand bereits geändert" — sauberer als stilles Schlucken, gerade
  weil bei RB-01 der Mensch die eigentliche Entscheidung trägt.
- **Alternativen:**
  - **Idempotent (zweites Ack → `200`, no-op)** — verworfen: schluckt versehentliche Doppel-Acks lautlos,
    schwächt die Audit-Klarheit (NF-09).
  - **Jedes Ack erneut loggen (mehrfaches Quittieren erlaubt)** — verworfen: bläht das Audit-Log mit
    redundanten Einträgen auf; relevant ist die eine Erst-Quittierung.
- **Ergebnis/Status:** umgesetzt in `openapi.yaml` (`409`-Response + Description, Auslösebedingung
  `acknowledged`/`cleared`), validiert, Teil von PR #48. Reaktion auf das Reviewer-Finding (Reviewer hatte
  `409` oder dokumentierte Idempotenz als Optionen genannt).

## 2026-06-24 — Taupunkt-Funktion als strikter Rechner: `ValueError` statt stillem Ersatzwert (DTB-32)
- **Kontext/Task:** DTB-32 (P2.3, Taupunkt nach Magnus) · NF-01 (Fail-safe) · Naht zu DTB-60 (Poller) und
  DTB-38 (Bewertung). Ich hatte `calculate_dew_point(air_temp_c, humidity_pct)` zuerst geradlinig
  implementiert (Magnus, a=17,62 / b=243,12 aus `Schwellenwerte.md §1`). Ein santa-loop-Review deckte zwei
  Fail-safe-Brüche an den Rändern auf: (1) bei `humidity_pct = 0` warf meine Funktion einen `ValueError`,
  während der Poller (`poller.py`) RH=0 durchlässt — eine **Naht-Kollision**, die im Bewertungspfad zu einem
  ungefangenen Absturz führen kann; (2) bei `air_temp_c = NaN` lieferte die Funktion ein **stilles `nan`**,
  das die spätere Bewertungskaskade über die ΔT-Vergleiche fälschlich auf **GRÜN** durchfallen lässt.
- **Entscheidung:** Die Funktion bleibt ein **strikter Rechner**. Bei nicht bestimmbarer oder ungültiger
  Eingabe (RH ∉ (0, 100], nicht-endliche Temperatur NaN/inf, Magnus-Pol bei T_a = −b) wirft sie einen
  **`ValueError`** und liefert bewusst **kein** stilles Ersatzergebnis. Die eigentliche Fail-safe-Reaktion
  (fehlender Taupunkt → konservativ ≥ GELB) baue ich **nicht** in diese Funktion ein, sondern lege sie als
  **dokumentierte Auflage** auf den Aufrufer: DTB-60 (Poller) muss den `ValueError` fangen und
  `dew_point_c = None` speichern; DTB-38 (Bewertung) stuft den fehlenden T_d konservativ ein.
- **Begründung:** Ich trenne bewusst **Berechnung** und **Sicherheits-Policy**. Die Aufgabe dieser reinen
  Funktion ist, einen Taupunkt zu rechnen **oder klar zu signalisieren, dass das nicht geht** — nicht, zu
  entscheiden, welche Ampelstufe daraus folgt. Diese Stufen-Entscheidung gehört in die Bewertungslogik
  (DTB-38), den hoch getesteten Kern. Eine geworfene Exception ist ein **explizites, fangbares Signal**;
  genau das ist der Gegenentwurf zum stillen `nan`, das wie eine gültige Zahl aussieht, sich weiterpflanzt
  und die Kaskade unbemerkt auf GRÜN kippt — der konkrete NF-01-Verstoß. Indem Berechnung und Policy in
  getrennten Modulen liegen, bleibt jedes für sich testbar, und die Naht-Inkonsistenz löse ich über einen
  **klaren Vertrag** (Aufrufer fängt und behandelt), nicht durch stilles Aufweichen einer Seite.
- **Alternativen:**
  - **`None`-Sentinel zurückgeben** (Signatur `float | None`): verworfen — verlagert die Policy zwar auch zum
    Aufrufer, aber `None` lässt sich leichter übersehen als eine Exception (ein vergessenes `if td is None`
    führt erneut zu stillem Fehlverhalten) und vermischt „kein Ergebnis" mit dem normalen Rückgabetyp. Eine
    Exception **erzwingt** eine bewusste Behandlung.
  - **Schema/Poller sofort mit anpassen** (`humidity_pct: Field(gt=0)`): verworfen für jetzt — würde den
    Scope von DTB-32 in DTB-12 (Datenmodell) und DTB-60 (Poller) ausweiten und mehrere Tickets/Tests
    berühren, bevor die Naht mit dem Architekten final abgestimmt ist. Kann später als eigene, bewusste
    Entscheidung folgen.
  - **Fail-safe-Default direkt in der Funktion** (z. B. bei RH=0 einfach T_a zurückgeben): verworfen — das
    wäre genau das stille, plausibel aussehende Ersatzergebnis, das NF-01 verbietet; die Funktion würde eine
    Sicherheitsentscheidung treffen, die ihr nicht zusteht.
- **Ergebnis/Status:** umgesetzt. `calculate_dew_point` mit Guards (RH-Bereich, `math.isfinite`,
  Magnus-Pol); 20 Unit-Tests grün, inkl. Frost-/Negativ-Referenzwerten (−2,1/92 → −3,225 °C;
  −10/80 → −12,797 °C) und Guard-Tests; Coverage `assessment` = 100 %. Branch
  `feat/dtb-32-taupunkt-magnus` gepusht (PR/Merge offen, Lucas-Freigabe). **Offene Folge-Auflage:** Bei der
  Umsetzung von DTB-60 den `ValueError` fangen → `dew_point_c = None` → DTB-38 fail-safe ≥ GELB; dort
  verifizieren.
