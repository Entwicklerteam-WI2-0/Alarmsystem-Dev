# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⛔ Pflichtlektüre & Source-of-Truth — VOR jeder Arbeit (verhindert Kontext-Misses)

**Maßgeblich ist der LIVE-Stand, nicht alte Planungs-Docs.** Bei jeder Task in dieser Reihenfolge orientieren:

1. **`erinnerung/stand.md`** — aktueller Gesamtstand + offene Punkte (zuerst).
2. **Live-Jira (Projekt `DTB`)** + offene GitHub-PRs — was real offen/erledigt ist.
3. **Anforderungen `02-Arbeitsdokumente/Usecase-quick.md`** (FA/NF/RB) — u. a. **RB-01** (kein Aktor) und **Alarm-Clearing = REIN MANUELL** (ein Mensch beendet den Alarm; **kein** Auto-Clear, kein `cleared_at`-Automatismus).
4. **Bewertungslogik `02-Arbeitsdokumente/Schwellenwerte.md`** (4 Stufen; Werte projektfinal → parametrierbar, NIE hardcoden).
5. **Architektur/Naht `02-Arbeitsdokumente/Backend-Konzept.md`** (§9 = G1→G2-Contract).
6. **Entscheidungen** `02-Arbeitsdokumente/Entscheidungslog-Lucas-Systemarchitektur.md` (zentral, E-xx) + `02-Arbeitsdokumente/Lucas-Entscheidungslog/Lucas-Entscheidungslog.md` (persönlich).

### API-Vertrag — EINGEFROREN (einhalten, NICHT „verbessern")
- **`04-Source-code/docs/API_FROZEN_v1.md`** = eingefrorener G1↔G2↔G3-Vertrag v1.0 (DTB-35).
- **`04-Source-code/docs/api/v1/openapi.yaml`** = formale G2-Spec · `g1-consumed.openapi.yaml` = konsumierter G1-Vertrag.
- **HARTE REGEL:** „API FROZEN" = **dagegen implementieren**, nicht umschreiben. Die Spec wird **NICHT** für Review-Nitpicks (enum/maxLength/Beschreibungen) editiert. Echte Änderungen nur über `/v2/` bzw. bewusste Architektenentscheidung. **Review-Befunde sammeln, priorisieren, NUR Blocker fixen** — kein Befund-für-Befund-Abarbeiten an einer eingefrorenen Datei.

### Bekannte Fakten (nicht erneut erfragen)
- **G3-Lead = Nick.** G1-Lead = Nils.
- Alarm-Clearing = **manuell** (FA / RB-01).
- Inter-Gruppen-Kommunikation (G1/G3) → als **versandfertige `.txt` auf den Desktop** legen.
- Aktiver Stand/Plan bis M3: siehe `erinnerung/stand.md` + Desktop-Plan (`Plan-bis-M3.md`).

> **Zweck:** Kontext-Misses und ineffizientes Nachfragen/Re-Editieren vermeiden. Im Zweifel: `stand.md` + Live-Jira + obige Doks lesen, dann handeln.

## ⚠️ Die „40 % Einzelleistung" ist NUR ein Prüfungs-Notengewicht — keine Arbeits-/Architekturregel

Die „40 % individuell / 60 % Gruppe" (aus `01-quellen/Prüfungsleistung Anforderungen.txt`) sind ausschließlich
der **Bewertungsschlüssel der Dozenten** für die Prüfungsnote. Sie haben **keinerlei** Bedeutung für die
Entwicklungsarbeit, die Architektur oder die Aufgabenverteilung. Agenten dürfen die 40 % **niemals** als Grund
verwenden, technische/architektonische Entscheidungen an einen Menschen „zurückzudelegieren" oder als
„individuell zu treffende" zu framen — und Arbeitsdokumente/Pläne/Begründungen **niemals** absichtlich als
Lücke leer lassen. Triff und empfiehl technische Entscheidungen **wie ein kompetenter Engineering-Partner**.
(Quelle der Klarstellung: `~/.claude/CLAUDE.md`, Lucas explizit 22.06.2026.)

## Was dieses Verzeichnis ist

Dies ist das **Arbeits-Repository der Backend-Gruppe (G2)** für den Projektkurs „Vereisungserkennung am
Flughafen ANR". Es enthält das Briefing-Rohmaterial (Text-Extrakte), die erarbeiteten Requirements-/
Design-Artefakte **und** (zunehmend) den **Backend-Code**. Die konkrete Stack-Wahl ist bewusst offen.

> **Repo-Rollen-Trennung (wichtig):** Dieses Repo ist die **Code-/Use-Case-Source** (Doku, Requirements,
> Backend-Code). Das **gesamte Claude-Tooling** — Skills, Commands, Hooks, das Team-OS — lebt
> **ausschließlich** im separaten Repo **`devteam-vibecodes`** und wird von dort via Setup/`git pull`
> verteilt. **Hierher kommt KEIN Skill, KEIN Command, KEIN Plugin, KEIN Tooling.**

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
  > ⚠️ **PROJEKTFINAL (Stand 2026-07-01):** Die eingetragenen Schwellen sind für diesen Prototyp
  > **final**. Messtechnisch validierte G1-Finalwerte sind **nicht mehr zu erwarten** (ein Sensor defekt,
  > einer nicht kalibrierbar) — die Werte wurden aus den Sensor-Datenblättern abgeleitet und an
  > Standort-Realdaten (ANR ≈ Coburg) plausibilisiert; endgültige Kalibrierung = 2-Jahres-Ausblick.
  > **Sie bleiben parametrierbar (NF-05): KEINE harte Verdrahtung — alle Schwellen über `config/`,
  > damit eine spätere Nachkalibrierung ohne Code-Änderung möglich ist.**
- `Backend-Konzept.md` — **Architektur der Backend-Gruppe** (Module, Datenmodell, Tech-Stack-Optionen, Code-Struktur). **§9 enthält den verbindlichen G1→G2 API-Vertrag** — siehe „API-/Datenmodell-Vertrag" unten.
- `Tasks+Projektplan.md` — Phasen **P0–P6**, Meilensteine M1–M3, Kanban-Tasks (Owner/DoD/Größe)
- `Team-Organisation+Regeln.md` — Rollen/DRI, Zusammenarbeits-Map, Teamregeln
- `assets/` — `WhatsApp Image …jpeg` (Architekturskizze) · Rollen-/Gruppeneinteilungs-Bilder
- Root `Agents-gpt-gemini.md` — **KI-Onboarding** (einfügbares Briefing für ChatGPT/Gemini)
- `03-abgaben/Nutzer und Stakeholdermodel 1.md` / `2.md` — Stakeholder-/Nutzermodell (abgabefertig)

> Die `.md`-Deliverables teilen sich **gemeinsame IDs** (FA/NF/RB/AE, K1–K9). Bei einer Klassifikations-/
> ID-Änderung **alle betroffenen Dokumente konsistent halten** (Drift-Gefahr).

### API-/Datenmodell-Vertrag (Mandatory Read)

Der verbindliche **G1→G2 API-Vertrag** ist in **`Backend-Konzept.md` §9** dokumentiert. Jeder Agent
**MUSST** diesen Abschnitt lesen, bevor er Code an der Naht zwischen Sensorik (G1) und Backend (G2)
schreibt oder verändert:

- G1 stellt eine eigene Sensor-API bereit; G2 pollt sie.
- `GET /current` liefert einen Snapshot mit gemeinsamem `measured_at` (Pflichtfeld).
- `GET /health` liefert `200` (ok) oder `503` (fault).
- Pflicht-Trias: `surface_temp_c`, `air_temp_c`, `humidity_pct`.
- `measured_at` und `/health` sind gegenüber G1 nicht verhandelbar.

**Direktlink:** `02-Arbeitsdokumente/Backend-Konzept.md` → Abschnitt 9 „Schnittstellen nach außen".

### Heutiger Stand (16.06.2026)

- **Vereisungs-Entscheidungslogik + Schwellenwerte konkretisiert** (`Schwellenwerte.md`): 4 Stufen über
  Oberflächentemp + Taupunkt-Abstand + Feuchte — löst beide dokumentierten Vorfälle korrekt auf. *(Niederschlag als Faktor gestrichen 22.06., Customer-Scope → E-32.)*
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
  −2,1 °C (kein Eis) und übersehene Eisbildung bei +1,2 °C. Relevant: **Oberflächentemperatur,
  Oberflächenfeuchte, Taupunkt** (umgesetzt in `Schwellenwerte.md`). *(Niederschlagsart gestrichen → E-32.)*
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
  > ⚠️ **SCHWELLEN PROJEKTFINAL:** Die Werte in `Schwellenwerte.md` sind für den Prototyp **final**
  > (G1-Finalwerte nicht mehr zu erwarten — Sensor defekt/nicht kalibrierbar; aus Datenblatt/Standort
  > plausibilisiert; Kalibrierung = 2-Jahres-Ausblick).
  > **Pflicht beim Feature-Bau:** Schwellen NIE hardcoden; ausnahmslos über `config/` parametrierbar
  > halten, damit eine spätere Nachkalibrierung ohne Refactoring möglich ist.
