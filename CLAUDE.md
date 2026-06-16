# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Was dieses Verzeichnis ist

Dies ist das **Arbeits-Repository der Backend-Gruppe (G2)** für den Projektkurs „Vereisungserkennung am
Flughafen ANR". Es enthält das Briefing-Rohmaterial (Text-Extrakte), die erarbeiteten Requirements-/
Design-Artefakte **und** (zunehmend) den **Backend-Code**. Die konkrete Stack-Wahl ist bewusst offen.

Versioniert mit **Git**; Remote: **`Entwicklerteam-WI2-0/Alarmsystem-Dev`** (GitHub, Team-Org), Branch `main`.
Lokaler Ordner: `C:\Users\LucasVöhringer\Desktop\Alarmsystem-Dev`.
Vor `push`/PR/`force-push`/destruktiven Git-Aktionen: **vorher Genehmigung einholen.**

> **Historie/Cleanup:** Frühere Repos/Ordner (`technology-engeneering`, `Backend Sensor POC`) sind
> **abgelöst** — **dieses** Repo (`Alarmsystem-Dev`) ist das **alleinige Arbeitsrepo** (Doku **und** Code).
> Das zentrale Team-Remote liegt in der GitHub-Org `Entwicklerteam-WI2-0`.

**Ordnerstruktur:**
- `01-quellen/` — Briefing-Rohmaterial vom Dozenten (read-only)
- `02-Arbeitsdokumente/` — erarbeitete RE-/Design-Artefakte (lebende Deliverables); Bilder in `02-Arbeitsdokumente/assets/`
- `03-abgaben/` — abgabefertige/eingefrorene Stände
- *(geplant)* `src/`, `tests/` — Backend-Code (Struktur s. `Backend-Konzept.md` §7)
- `CLAUDE.md` / `AGENTS.md` / `Agents-gpt-gemini.md` im **Root** (gitignored)

### Quelldokumente (Briefing-Rohmaterial, read-only — in `01-quellen/`)

- `01-quellen/Studierenden-Handreichung.txt` — Aufgabenstellung, Rollen, Gruppen, Vorgehensmodelle, Meilensteine, Bewertung
- `01-quellen/Die Hintergrundgeschichte.txt` — **bewusst widersprüchliches/unvollständiges Rohmaterial** (E-Mails,
  Chats, Protokolle, Vorfallberichte). Primärquelle für das Requirements Engineering
- `01-quellen/Zeitplan.txt` — 3-Wochen-Zeitplan mit Meilensteinen M1–M3
- `01-quellen/Prüfungsleistung Anforderungen.txt` — Bewertungskriterien (40 % individuell / 60 % Gruppe) + Liste der Pflichtdokumente

> Die ursprünglichen PDFs liegen **nicht mehr** im Verzeichnis; maßgeblich sind die `.txt`-Extrakte oben.

### Erarbeitete Artefakte (in `02-Arbeitsdokumente/`, werden laufend gepflegt)

- `Usecase-quick.md` — Anforderungen: funktional **FA-01–12**, nicht-funktional **NF-01–11**, harte Randbedingung
  **RB-01**, offene Entscheidungen **AE-01/AE-02**, Konfliktanalyse **K1–K9** (§4)
- `Schwellenwerte.md` — **Vereisungslogik + konkrete Schwellenwerte** (4 Stufen 🟢🟡🟠🔴) und Kalibriervorgaben je FA/NFA
- `Backend-Konzept.md` — **Architektur der Backend-Gruppe** (Module, Datenmodell, Tech-Stack-Optionen, Code-Struktur)
- `Tasks+Projektplan.md` — Phasen **P0–P6**, Meilensteine M1–M3, Kanban-Tasks (Owner/DoD/Größe)
- `Team-Organisation+Regeln.md` — Rollen/DRI, Zusammenarbeits-Map, Teamregeln
- `assets/` — `WhatsApp Image …jpeg` (Architekturskizze) · Rollen-/Gruppeneinteilungs-Bilder
- Root `Agents-gpt-gemini.md` — **KI-Onboarding** (einfügbares Briefing für ChatGPT/Gemini)
- `03-abgaben/Nutzer und Stakeholdermodel 1.md` / `2.md` — Stakeholder-/Nutzermodell (abgabefertig)

> Die `.md`-Deliverables teilen sich **gemeinsame IDs** (FA/NF/RB/AE, K1–K9). Bei einer Klassifikations-/
> ID-Änderung **alle betroffenen Dokumente konsistent halten** (Drift-Gefahr).

### Heutiger Stand (16.06.2026)

- **Vereisungs-Entscheidungslogik + Schwellenwerte konkretisiert** (`Schwellenwerte.md`): 4 Stufen über
  Oberflächentemp + Taupunkt-Abstand + Feuchte + Niederschlag — löst beide dokumentierten Vorfälle korrekt auf.
- **Backend-Konzept** (auf G2 geschnitten) und **Projektplan/Kanban** (`Tasks+Projektplan.md`) erstellt.
- **KI-Onboarding** für ChatGPT/Gemini (`Agents-gpt-gemini.md`).
- **Rolle/Gruppe bestätigt:** G2 Backend; Lucas = Systemarchitekt.
- Repo konsolidiert auf `Alarmsystem-Dev`; Doku in `01/02/03`-Struktur. Umbenennungen/Ablösungen:
  Stakeholderanalyse → *Nutzer-und-Stakeholdermodel*; Randbedingungsmetriken → *Schwellenwerte*;
  *Architektur-Stack-Konzept* (zu breit) → abgelöst durch das fokussierte *Backend-Konzept*.

## Kernauftrag des Projekts

Prototypisches System zur **Erfassung und Bewertung von Vereisungsbedingungen** an einem
Regionalflughafen in Mittelgebirgslage. Fünf Komponenten:

1. Sensordatenerfassung
2. Datenverarbeitung
3. Backend-System
4. Visualisierung (Frontend)
5. Vereisungsbewertung (Entscheidungslogik)

**Zentrale Eigenheit:** Es existiert keine saubere Spezifikation. Das Lastenheft muss aus dem
widersprüchlichen Material in `Die Hintergrundgeschichte.txt` **erst hergeleitet** werden — das ist
ausdrücklich Teil der Aufgabe und der Bewertung. Das Briefing nie als fertige Spec behandeln.

**Arbeitsannahme ANR ≈ Flugplatz Coburg:** Für reale Sensor-/Standort-/Regionalrecherche bildet das
Team den fiktiven Flughafen ANR auf den realen Regionalflugplatz Coburg ab. Dies ist eine **dokumentierte
Annahme**, keine Briefing-Vorgabe.

## Harte Randbedingungen & Designentscheidungen (aus der Hintergrundgeschichte abgeleitet)

- **Sicherheitskritisch — keine Automatik-Freigabe:** Das System darf die Startbahn NIE automatisch
  freigeben oder sperren. Die Verantwortung bleibt beim Menschen. Entscheidungs*unterstützung*, kein Aktor. (→ RB-01)
- **Lufttemperatur reicht nicht:** Beide Vorfälle scheiterten an reiner Lufttemperatur — Fehlalarm bei
  −2,1 °C (kein Eis) und übersehene Eisbildung bei +1,2 °C. Relevant: **Oberflächentemperatur, Feuchte,
  Taupunkt, Niederschlagsart** (umgesetzt in `Schwellenwerte.md`).
- **Zielkonflikt Fehlalarm vs. Sicherheit:** „Lieber zehn Fehlalarme als ein vereistes Flugzeug" — Kern der
  Bewertungslogik, bewusst parametrierbar. (→ K1)
- **Vorhersage statt Momentaufnahme:** Fluglotsen brauchen ≥ 30 min Vorlaufzeit.
- **Wartbarkeit der Sensoren:** Vorfeld-Sensoren werden beschädigt — Robustheit/Austauschbarkeit einplanen.
- **Betriebsmodell offen:** lokal vs. Cloud + Fernzugriff begründet dokumentieren. (→ AE-01/AE-02)
- **Budgetdruck:** Referenzsensor WX-500 ~4.800 €/Stück; Sensoranzahl/-auswahl begründen.
- **Risiken R1–R5:** falsche Sensordaten, Kommunikations-/Stromausfall, nicht erkannte Vereisung, zu viele Fehlalarme.

## Arbeitsorganisation (3 Gruppen, bewusster Methodenvergleich)

- **Gruppe 1 — Sensorik & Daten** (Wasserfall): Sensoren recherchieren, Datenblätter, Auswahl, Messung
- **Gruppe 2 — Backend & Entscheidungslogik** (Wasserfall, **= dieses Team**): Datenmodell, API, Speicherung, Vereisungsbewertung
- **Gruppe 3 — Frontend & Integration** (Scrum): Nutzeroberfläche, Visualisierung, Alarmierung, Integration

Die Schnittstelle zwischen den Gruppen ist die **API/das Datenmodell** (Gruppe 2) — laut Zeitplan bis Ende
Woche 2 final. In `Backend-Konzept.md` ist dies als die *einzige* Naht herausgearbeitet, die früh einzufrieren ist.

### Unser Team — Gruppe 2 (Backend & Entscheidungslogik)

Rollenverteilung (Stand 16.06.2026; Namen ggf. korrigieren):

| Rolle | Personen |
|---|---|
| Teilprojektleiter | Landmann, Lucas |
| Systemarchitekt | **Vöhringer, Lucas** · Petzold, Johannes |
| Backend-Entwickler | Hartling, Leon · Ganter, Luca · Moritz, Andreas · Sarkhab, Arash · (Vöhringer, Lucas) |
| Test | Mohammadi, Azezoo · Berger, Amelie |
| Dokumentation | Reisi, Maryam · Ilchyshyn, Vladyslav |

**Lucas (ArchiDox) = Systemarchitekt** (primär) + unterstützend Backend-Entwickler. Damit gehört ihm
fachlich die **API/Datenmodell-Naht** und das `Backend-Konzept.md`. Gruppe = Backend/G2.

## Deliverables & Meilensteine

Pflicht-Dokumentation: **versioniertes Lastenheft**, Architekturdiagramm, API-Beschreibung, Sensordatenanalyse,
**Entscheidungslogbuch**. Phasen/Tasks: s. `Tasks+Projektplan.md`.

- **M1 (Ende Woche 1):** Stakeholderanalyse, erste Anforderungen, Sensorkandidaten, Architekturideen, dokumentierte
  Konflikte — *liegt im Entwurf vor (Usecase-quick, Schwellenwerte, Backend-Konzept, Stakeholder-/Nutzermodell)*.
- **M2 (Ende Woche 2):** funktionierende Einzelmodule, **API & Datenmodell final**, erste E2E-Teilintegration, getestete Pipeline.
- **M3 (Abschluss):** vollständiger Prototyp, Live-Demo, Abschlusspräsentation, validierte Vereisungslogik, Reflexion + Methodenvergleich.

Bewertet werden v. a.: Nachvollziehbarkeit technischer Entscheidungen, Datenanalyse, Umgang mit widersprüchlichen
Anforderungen, technische Umsetzung, Teamorganisation, Reflexion.

## Konventionen

- Sprache aller Artefakte: **Deutsch**.
- **Versionskontrolle:** Git, Remote `Entwicklerteam-WI2-0/Alarmsystem-Dev` (GitHub), Branch `main`.
  **Workflow:** Feature-Branch → PR → Review → `main` (main bleibt lauffähig). **Ausgehende/destruktive
  Git-Aktionen (push, PR, merge, force-push) nur nach expliziter Genehmigung.** Keine Secrets committen.
- **Build-/Test-/Lint-Kommandos und Tech-Stack** sind noch nicht final — Stack-Wahl ist offen und gehört
  begründet ins Entscheidungslogbuch (Optionen in `Backend-Konzept.md` §6; Empfehlung T0: FastAPI + SQLite + HTTP).
- Funktionale Vorgehensweise: **vom Kernpfad (T0) ausgehen**, Features als T1–T3 aufsetzen (s. `Backend-Konzept.md` / `Tasks+Projektplan.md`).
- **Vereisungslogik/Schwellenwerte** ausschließlich aus `Schwellenwerte.md` — nichts dazuerfinden; Defaults parametrierbar.
