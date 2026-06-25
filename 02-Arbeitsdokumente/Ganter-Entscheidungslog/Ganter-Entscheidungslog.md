# Persönliches Entscheidungslog — Luca Ganter (G2)
> **Erstellt am:** 2026-06-23 · **Letzte Bearbeitung:** 2026-06-23
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
