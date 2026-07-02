# Backend-Abschlusspräsentation (G2) — Struktur & Sprecher-Leitfaden

> **Slot:** 45 min · Gruppe 2 (Backend & Entscheidungslogik) · Abschluss M3 (02.07.2026)
> **Format:** Marp (Markdown → PDF, beamer-safe) · Deck: `01-backend-deck.md`
> **Publikum:** Dozenten + Plenum · Bewertet nach den 6 Kriterien (siehe unten)
> **Hauptsprecher:** **Lucas** (Systemarchitekt, Dreh- & Angelpunkt G2) — führt durch **alles**.
> **Kurze Fach-Übergaben:** **Johannes** (Edge Cases + Testsuite) · **Andi** (Betrieb / Raspberry-Pi-Setup).

---

## Leitidee — Storyline statt Kriterien-Abklappern

45 Minuten trägt eine **Erzählung**, keine Aufzählung. Roter Faden:

> **„Ein Flughafen mit zwei realen Vorfällen und widersprüchlichem Briefing — wir haben daraus ein
> fail-safe Entscheidungssystem gebaut, das genau diese zwei Fehler nicht mehr macht."**

Die 6 Bewertungskriterien werden **in die Story eingebettet**, nicht als Kapitel gelesen. Jede
Folie trägt unten rechts ein dezentes Kriterien-Tag (für die Dozenten sichtbar, für die Story unaufdringlich).

| # | Bewertungskriterium | wird bedient in Akt |
|---|---|---|
| ① | Umgang mit widersprüchlichen Anforderungen | 1 (Chaos) + 3 (MySQL-Zwang) |
| ② | Nachvollziehbarkeit technischer Entscheidungen | 3 (Die Weichen) |
| ③ | Qualität der Datenanalyse | 2 (Die Erkenntnis) |
| ④ | Technische Umsetzung (Prototyp + Live-Demo) | 4 (System) + 5 (Demo) |
| ⑤ | Teamorganisation | 6 (Team & Methode) |
| ⑥ | Reflexion | 7 (Ehrliche Reflexion) |

---

## Zeit-Choreografie (45 min, mit Puffer)

| Akt | Titel | Zeit | Sprecher | Kernbotschaft |
|---|---|---|---|---|
| 0 | Titel + Agenda | 1' | Lucas | Wer wir sind, wohin die Reise geht |
| 1 | **Das Chaos** | 5' | Lucas | 2 reale Vorfälle + widersprüchliches Rohmaterial → Lastenheft |
| 2 | **Die Erkenntnis** | 5' | Lucas | Lufttemperatur lügt → 3-Faktor (Oberfläche + Taupunkt + Feuchte) |
| 3 | **Die Weichen** | 8' | Lucas | Push→Pull, **MySQL von oben**, SQLAlchemy/Docker verworfen |
| 4 | **Das System** | 10' | Lucas → **Johannes (3')** | Datenmodell, API frozen, 4-Stufen-Kaskade, Fail-safe (6 Schichten) → *Johannes: wie wir das testen* |
| 5 | **Der Beweis (Live-Demo)** | 8' | Lucas → **Andi (2')** | Ampel grün→rot→Alarm→Ack→fault→recovery → *Andi: läuft real auf dem Pi* |
| 6 | **Team & Methode** | 4' | Lucas | Wasserfall, DRI, Contract-first entblockt Parallelarbeit |
| 7 | **Ehrliche Reflexion** | 3' | Lucas | „Tests grün ≠ Produkt läuft"; offene Punkte ehrlich benannt |
| — | Q&A-Puffer | 1' | alle | |

> **Timing-Disziplin:** Akt 4 + 5 sind das Herz (18'). Wenn die Zeit knapp wird, kürze Akt 6 auf 2'
> und Q&A fällt in die Pause — Akt 4/5 **nie** kürzen (das ist die technische Umsetzung = Kriterium ④).

---

## Sprecher-Übergaben — konkrete Formulierungen

**Lucas → Johannes (Ende Akt 4, beim Fail-safe/Testing):**
> „Ein fail-safe System ist nur so gut wie die Fälle, gegen die es getestet wurde. Johannes hat die
> Edge Cases und die Testsuite aufgebaut — Johannes, zeig, wie wir das System *gebrochen* haben,
> bevor es der Winter tut."

**Johannes → Lucas (zurück):**
> „…und genau dieser NaN-Guard-Fund ist ein Beispiel dafür, warum wir adversarial testen. Zurück zu
> dir, Lucas — jetzt sehen wir es live."

**Lucas → Andi (in Akt 5, Live-Demo läuft):**
> „Was ihr hier live seht, läuft nicht auf meinem Laptop, sondern auf echter Hardware. Andi hat das
> Deployment auf dem Raspberry Pi mit MariaDB aufgesetzt — Andi, wie kommt das System in den Betrieb?"

**Andi → Lucas (zurück):**
> „…und damit ist es genau die Zielumgebung, die die Geschäftsleitung wollte. Lucas, dein Fazit."

---

## Foliensatz-Gliederung (Deck `01-backend-deck.md`)

| Folie | Akt | Inhalt | Kriterium-Tag |
|---|---|---|---|
| 1 | 0 | **Titel** — Vereisungserkennung ANR · G2 Backend · Team + Rollen | — |
| 2 | 0 | **Agenda** — die 7 Akte als roter Faden | — |
| 3 | 1 | **Der Auftrag** — Flughafen ANR, Winterproblem, unsere Rolle als Ingenieurteam | ① |
| 4 | 1 | **Die 2 Vorfälle** — Fehlalarm −2,1 °C · übersehene Vereisung +1,2 °C | ① |
| 5 | 1 | **Das Rohmaterial** — E-Mails/Chats/Notizen: unvollständig & widersprüchlich → Lastenheft (FA/NF/RB) | ① |
| 6 | 2 | **Warum Lufttemperatur lügt** — beide Vorfälle mit reiner Lufttemp falsch | ③ |
| 7 | 2 | **Die 3-Faktor-Logik** — Oberflächentemp + Taupunkt (Magnus) + ΔT | ③ |
| 8 | 2 | **Sensor-Datenbasis** — Datenblätter (DS18B20/BME280), ANR≈Coburg, Kalibrierung | ③ |
| 9 | 3 | **Die Weichen (Übersicht)** — 4 Schlüsselentscheidungen als Landkarte | ② |
| 10 | 3 | **MySQL von oben** — Geschäftsleitungs-Vorgabe → kritisch bewertet → umgesetzt (E-29) | ①② |
| 11 | 3 | **Push → Pull** — „Realität schlägt Empfehlung" (E-30→E-31) | ② |
| 12 | 3 | **Bewusst weggelassen** — SQLAlchemy + Docker verworfen: zu schwer fürs 3-Wochen-Team (E-35) | ② |
| 13 | 4 | **Architektur-Überblick** — Module + Datenfluss (Mermaid) | ④ |
| 14 | 4 | **Datenmodell** — Entitäten + Enums | ④ |
| 15 | 4 | **Die API (frozen v1)** — Endpoints G1-Pull / G3-Serve / SSE | ④ |
| 16 | 4 | **Die 4-Stufen-Kaskade** — 🟢🟡🟠🔴 mit Schwellen | ④ |
| 17 | 4 | **Fail-safe (NF-01)** — nie GRÜN bei Ausfall: 6 Schichten | ④ |
| 18 | 4 | **[JOHANNES] Edge Cases + Testsuite** — adversarial testen, NaN-Guard-Fund (DTB-38) | ④⑥ |
| 19 | 5 | **Live-Demo** — Drehbuch-Kurzfassung (Lucas fährt; Details in bestehendem Demo-Konzept) | ④ |
| 20 | 5 | **[ANDI] Betrieb** — Raspberry Pi + MariaDB, so läuft es real | ④⑤ |
| 21 | 6 | **Team & Methode** — Wasserfall, Rollen/DRI, Contract-first | ⑤ |
| 22 | 7 | **Reflexion** — was lief gut / was war schwer / was bleibt offen | ⑥ |
| 23 | 7 | **Ausblick + Schluss** — echte Kalibrierung, Cloud-Option; Kernbotschaft | ⑥ |
| B1–B3 | Backup | Demo-Fallback-Screenshots (`ALLE N PASS`), Detail-Schwellen, K1-Konflikt | — |

---

## Demo-Slot (Akt 5) — Hinweis
Die Live-Demo ist bei Lucas **bereits konzipiert und geplant** (12-Schritte-Showcase / Live-Sim). Dieses
Deck liefert nur die **Rahmenfolie** (Folie 19) + Andis Betriebs-Einschub (Folie 20). Fallback-Screenshots
liegen als Backup-Folien B1 hinten. → Demo-Inhalt nicht hier duplizieren.

---

## Nächste Bau-Schritte (nach diesem Leitfaden)
1. `01-backend-deck.md` — vollständiges Marp-Deck mit echten Zahlen aus den drei Faktenblättern.
2. Sprechernotizen je Folie als Marp-Presenter-Notes (`<!-- ... -->`).
3. Mermaid-Architekturdiagramm einbetten (aus Architekturdiagramm.md).
4. PDF-Export testen (`marp 01-backend-deck.md --pdf`).
