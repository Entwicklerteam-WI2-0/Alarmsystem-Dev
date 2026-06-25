# AGENTS.md – Projektkurs: Vereisungserkennung am Flughafen ANR

> Diese Datei richtet sich an KI-Coding-Agenten, die an diesem Projekt arbeiten.
> Sie beschreibt den aktuellen Stand auf Grundlage der tatsächlich vorhandenen Dateien.
> Sprache: Deutsch (wie alle Projektdokumente).
> **Hinweis:** Dieses Repo ist das **Arbeitsrepo der Backend-Gruppe (G2)** — `Entwicklerteam-WI2-0/Alarmsystem-Dev`.

> ## ⚠️ Die „40 % Einzelleistung" ist NUR ein Prüfungs-Notengewicht — keine Arbeits-/Architekturregel
> Die „40 % individuell / 60 % Gruppe" sind ausschließlich der **Bewertungsschlüssel der Dozenten** für die
> Prüfungsnote. Sie haben **keinerlei** Bedeutung für die Entwicklungsarbeit, die Architektur oder die
> Aufgabenverteilung. **Agenten dürfen die 40 % NIEMALS** als Grund verwenden, technische/architektonische
> Entscheidungen an einen Menschen „zurückzudelegieren" oder als „individuell zu treffende" zu framen — und
> dürfen Arbeitsdokumente/Pläne/Begründungen **niemals** absichtlich als Lücke „für den Menschen" leer lassen.
> Triff und empfiehl technische Entscheidungen **wie ein kompetenter Engineering-Partner**, mit klarer
> Empfehlung. Lucas ist PM/CTO/Architekt — er gibt Richtung, der Agent bringt Entscheidungstiefe.

---

## 1. Projektübersicht

Materialien für einen **studentischen Projektkurs** zur Entwicklung eines **prototypischen Systems zur
Erfassung und Bewertung von Vereisungsbedingungen** am fiktiven Flughafen **ANR (Airport North Regional)**.

**Stand:** Die **Anforderungs-/Planungsphase ist weitgehend abgeschlossen** (Anforderungen, Schwellenwerte,
Backend-Konzept, Projektplan liegen vor). Das Repo geht in die **Implementierungsphase** über — Quellcode
(`src/`, `tests/`) entsteht hier. Der Technologiestack ist final: **Python + FastAPI + rohes PyMySQL + native MariaDB** (kein SQLAlchemy/Alembic/Docker, E-35).

> **Repo-Rollen-Trennung (wichtig):** Dieses Repo ist die **Code-/Use-Case-Source** (Doku, Requirements,
> Backend-Code). Das **gesamte Claude-Tooling** — Skills, Commands, Hooks, das Team-OS — lebt
> **ausschließlich** im separaten Repo **`devteam-vibecodes`** und wird von dort via Setup/`git pull`
> verteilt. **Hierher kommt KEIN Skill, KEIN Command, KEIN Plugin, KEIN Tooling.**

### Kernziele

- Erfassung relevanter Oberflächendaten (Oberflächentemperatur, Oberflächenfeuchte, Taupunkt, Luftdruck). *(Niederschlagsart entfällt — Customer-Scope, → Entscheidungslog E-32.)*
- **Bewertung von Vereisungsrisiken** (Entscheidungslogik, s. `Schwellenwerte.md`).
- Backend zur Datenverarbeitung und Entscheidungsunterstützung (**unser Fokus, G2**).
- Visualisierung/Alarmierung über ein Frontend (G3), Sensorik (G1).
- Funktionierender Gesamtprototyp.

### Zentrale Eigenheit

Es existiert **keine saubere Spezifikation**. Das Lastenheft muss aus dem widersprüchlichen Material in
`01-quellen/Die Hintergrundgeschichte.txt` erst hergeleitet werden — das ist ausdrücklich Teil der Aufgabe
und der Bewertung. Das Briefing nie als fertige Spec behandeln.

### Harte Randbedingungen (aus der Hintergrundgeschichte abgeleitet)

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

### Rahmenbedingungen (bewusst widersprüchlich)

- **Sicherheit vs. Betriebskosten:** Sicherheit bevorzugt Fehlalarme, Betrieb will keine unnötigen Sperrungen.
- **Messgrößen:** Lufttemperatur allein reicht nicht — **Oberflächentemperatur** ist entscheidend.
- **Verantwortung:** Keine automatische Startbahnfreigabe durch das System — der **Mensch entscheidet** (RB-01).
- **Vorhersagehorizont:** mindestens **30 Minuten** Vorlauf.

---

## 2. Projektstruktur

Repo `Alarmsystem-Dev` (Remote `Entwicklerteam-WI2-0/Alarmsystem-Dev`, Branch `main`), gegliedert in:

- `01-quellen/` — Briefing-Rohmaterial vom Dozenten (`.txt`, read-only)
- `02-Arbeitsdokumente/` — erarbeitete `.md`-Deliverables; Bilder in `02-Arbeitsdokumente/assets/`
- `03-abgaben/` — abgabefertige/eingefrorene Stände
- `CLAUDE.md` / `AGENTS.md` / `Agents-gpt-gemini.md` im **Root** (gitignored; Auto-Load bzw. Chat-KI-Briefing)

| Datei | Inhalt |
|-------|--------|
| `01-quellen/Die Hintergrundgeschichte.txt` | Hintergrundgeschichte ANR: Vorfälle, E-Mails, Chats, Gutachten, unvollständiger Lastenheft-Entwurf |
| `01-quellen/Studierenden-Handreichung.txt` | Aufgabenstellung, Rollen, Gruppen, Vorgehensmodelle, Meilensteine, Bewertung |
| `01-quellen/Zeitplan.txt` | Wochenplanung (Analyse/Anforderungen, Entwicklung/Prototyping) |
| `01-quellen/Prüfungsleistung Anforderungen.txt` | Bewertungskriterien (40 % individuell / 60 % Gruppe) + Pflichtdokumente |
| `02-Arbeitsdokumente/Usecase-quick.md` | Usecase + Anforderungen (FA, NF, RB-01, AE, Konflikte K1–K9) |
| `02-Arbeitsdokumente/Schwellenwerte.md` | **Vereisungslogik + konkrete Schwellenwerte** (4 Stufen) + Kalibriervorgaben je FA/NFA — ⚠️ **DUMMY-WERTE, s. u.** |
| `02-Arbeitsdokumente/Backend-Konzept.md` | Architektur der Backend-Gruppe: Module, Datenmodell, Tech-Stack-Optionen, Code-Struktur. **§9 enthält den verbindlichen G1→G2 API-Vertrag (Mandatory Read).** |
| `02-Arbeitsdokumente/Tasks+Projektplan.md` | Phasen P0–P6, Meilensteine M1–M3, Kanban-Tasks (Owner/DoD/Größe) |
| `02-Arbeitsdokumente/Team-Organisation+Regeln.md` | Rollen/DRI, Zusammenarbeits-Map, Teamregeln |
| `02-Arbeitsdokumente/teamstruktur-final.md` | **Finale Rollenaufteilung** des aktiven Entwicklerteams inkl. Begründung |
| `02-Arbeitsdokumente/assets/` | Architekturskizze (WhatsApp-Bild) + Rollen-/Gruppeneinteilungsbilder |
| `03-abgaben/Nutzer und Stakeholdermodel 1.md` / `2.md` | Stakeholder-/Nutzermodell (abgabefertig) |
| `Agents-gpt-gemini.md` (Root) | KI-Onboarding (einfügbares Briefing für ChatGPT/Gemini) |
| `CLAUDE.md` / `AGENTS.md` (Root) | Projekt-/Agenten-Briefing |

> Frühere Dateien sind abgelöst/umbenannt: *Stakeholderanalyse* → *Nutzer-und-Stakeholdermodel*;
> *Randbedingungsmetriken* → *Schwellenwerte*; *Architektur-Stack-Konzept* (zu breit) → *Backend-Konzept* (G2-scoped).
> Ursprüngliche PDFs liegen nicht mehr vor; maßgeblich sind die `.txt`-Extrakte.

> [!WARNING]
> **DUMMY-SCHWELLENWERTE — Nachlieferung durch G1 ausstehend**
>
> Die in `Schwellenwerte.md` eingetragenen numerischen Grenzwerte (Temperaturen, Taupunkt-Abstände,
> Feuchte-Grenzen usw.) sind **vorläufige Platzhalterwerte**, die auf Basis der Hintergrundgeschichte
> eigenständig abgeschätzt wurden. Sie wurden **nicht messtechnisch validiert** und sind **nicht
> abgestimmt** mit Gruppe 1 (Sensorik & Daten).
>
> **Was noch aussteht:** Gruppe 1 liefert die echten, sensorspezifisch kalibrierten Schwellenwerte
> nach. Diese ersetzen die Dummies vollständig.
>
> **Konsequenz für Feature-Entwicklung (PFLICHT):**
> - Schwellenwerte dürfen **niemals hardgecoded** werden.
> - Alle Grenzwerte **ausnahmslos** über `config/` parametrierbar halten.
> - Code, Tests und Konfigurationen müssen den **Austausch durch G1-Finalwerte ohne Refactoring** ermöglichen.
> - Bis zur Finallieferung von G1: Dummies nur als **Testfixtures/Entwicklungsstände** behandeln,
>   nicht als fachlich korrekte Werte.

### API-/Datenmodell-Vertrag (Mandatory Read)

Der verbindliche **G1→G2 API-Vertrag** ist in **`02-Arbeitsdokumente/Backend-Konzept.md` §9**
dokumentiert. Jeder Agent muss diesen Abschnitt lesen, bevor er an der Naht arbeitet:

- G1 stellt eine Sensor-API bereit; G2 pollt sie.
- `GET /current` → Snapshot mit gemeinsamem `measured_at` (Pflichtfeld, ISO-8601 UTC).
- `GET /health` → `200 OK` oder `503 Service Unavailable`.
- Pflicht-Trias für die Bewertung: `surface_temp_c`, `air_temp_c`, `humidity_pct`.
- `measured_at` und `/health` sind gegenüber G1 **nicht verhandelbar**.

**Direktlink:** `02-Arbeitsdokumente/Backend-Konzept.md` → Abschnitt 9 „Schnittstellen nach außen".

### Heutiger Stand (16.06.2026)

Vereisungslogik + Schwellenwerte konkretisiert, Backend-Konzept (G2) und Projektplan/Kanban erstellt,
KI-Onboarding für ChatGPT/Gemini, Rolle/Gruppe bestätigt (G2 Backend; Lucas = Systemarchitekt),
Repo auf `Alarmsystem-Dev` konsolidiert, finale Teamstruktur in `teamstruktur-final.md` dokumentiert.

---

## 3. Team & Rollen

Aktive Rollenaufteilung (final) gemäß `02-Arbeitsdokumente/teamstruktur-final.md`:

| Sub-Team / Rolle | Personen | Kernverantwortung (DRI) |
|---|---|---|
| **Backend-Developer** | Arash · Luca | Ingest, Geschäftslogik, **Vereisungs-Bewertungslogik**, API-Implementierung |
| **Datenbank-Engineers** | Andreas · Leon | Datenbankschema, Repository-Pattern, Persistenz, Datenintegrität, Abfrageoptimierung |
| **Architekten** | Lucas · Johannes | API-Design, Datenmodell (Naht zu G1/G3), Architekturentscheidungen, technische Unterstützung der aktiven Entwickler |
| **Test & Code-Review** | Arezo · Amelie | Testfälle, Testprotokoll, Definition-of-Done, Code-Review |

**Lucas (ArchiDox) = Systemarchitekt** (primär). Damit gehört ihm fachlich die **API/Datenmodell-Naht**
und das `Backend-Konzept.md`. Gruppe = Backend/G2.

### Arbeitsorganisation (3 Gruppen, bewusster Methodenvergleich)

- **Gruppe 1 — Sensorik & Daten** (Wasserfall): Sensoren recherchieren, Datenblätter, Auswahl, Messung
- **Gruppe 2 — Backend & Entscheidungslogik** (Wasserfall, **= dieses Team**): Datenmodell, API, Speicherung, Vereisungsbewertung
- **Gruppe 3 — Frontend & Integration** (Scrum): Nutzeroberfläche, Visualisierung, Alarmierung, Integration

Die Schnittstelle zwischen den Gruppen ist die **API/das Datenmodell** (Gruppe 2) — laut Zeitplan bis Ende
Woche 2 final. In `Backend-Konzept.md` ist dies als die *einzige* Naht herausgearbeitet, die früh einzufrieren ist.

---

## 4. Technologiestack

Der Stack ist **final** (FastAPI + rohes PyMySQL + native MariaDB, E-35; begründet im Entscheidungslogbuch E-29/E-35).
Optionen + Empfehlung in **`Backend-Konzept.md` §6**:

- **Backend:** Python **FastAPI** (Empfehlung) · Flask · Node/Express
- **Datenbank:** **MySQL 8 / MariaDB** (GL-Vorgabe, durchgängig ab T0; native MariaDB, kein Docker, rohes PyMySQL statt ORM → E-29/E-35)
- **Datenabruf:** **HTTP-Pull** — G2 pollt G1s `GET /current` (Snapshot + `measured_at`) + `GET /health`, Intervall ≤ 60 s selbst bestimmt (→ E-31) → MQTT (Skalierung)
- **Sensorik (G1, Kontext):** ESP32/Raspberry Pi; IR-/Kontaktsensor Oberflächentemp; Kombisensor Temp/Feuchte/Druck (BME280/SHT31); Eisindikator zunächst Proxy/Sim.

**Offene Architekturentscheidungen** (vgl. `Usecase-quick.md` §3.4, AE-01/AE-02): lokal vs. Cloud + Fernzugriff,
Protokoll (HTTP/MQTT), DB-/Framework-Wahl.

---

## 5. Code-Organisation (Backend, G2)

Modul-/Ordnerstruktur s. **`Backend-Konzept.md` §7**:

```text
src/
  ingest/      # Poller (holt `GET /current` von G1), Eingangsvalidierung
  model/       # Datenklassen/Schemas
  assessment/  # Vereisungslogik (Schwellenwerte) — Kernmodul, hohe Testabdeckung
  storage/     # DB-Zugriff (Repository-Pattern)
  api/         # Serving-Endpoints für G3
  config/      # parametrierbare Schwellen
  forecast/    # 30-min-Trend (T3)
tests/
```

Zentrale Schnittstelle aller Gruppen = **API/Datenmodell der Gruppe 2**, bis Ende Woche 2 final.
**Scope-Abgrenzung:** G2 baut Backend; Sensor-Hardware = G1, UI = G3. Wir definieren nur den API-Vertrag.

---

## 6. Build- und Testbefehle

Stack final (FastAPI + PyMySQL + MariaDB, E-35). Befehle:

```bash
# Abhängigkeiten installieren (venv empfohlen)
cd 04-Source-code
uv sync

# Tests ausführen
pytest

# Backend starten (dev)
uv run python -m src.main
```

---

## 7. Code-Style und Entwicklungskonventionen

- **Sprache:** alle Artefakte, Doku, Kommentare auf **Deutsch**.
- **Versionskontrolle:** Git, Remote `Entwicklerteam-WI2-0/Alarmsystem-Dev` (GitHub), Branch `main`.
  **Workflow:** Feature-Branch → PR → Review → `main` (main bleibt lauffähig). **Ausgehende/destruktive
  Git-Aktionen (push, PR, merge, force-push) nur nach expliziter Genehmigung.** Keine Secrets committen.
- **Dokumentationspflicht:** jedes technische Ergebnis nachvollziehbar dokumentieren.
- **Entscheidungen begründen** (Alternativen/Gründe/Unsicherheiten) → **Entscheidungslogbuch**.
- **Lastenheft versioniert**, iterativ verfeinert.
- **Hybride Methodik:** G1/G2 Wasserfall, G3 Scrum; Schnittstellen früh definieren.
- **Sicherheitskritikalität:** jede Entscheidung gegen Fehlalarme/nicht erkannte Vereisung abwägen.
- **Vereisungslogik/Schwellenwerte ausschließlich aus `Schwellenwerte.md`** — nichts dazuerfinden; Defaults parametrierbar.
  **⚠️ Schwellen in `Schwellenwerte.md` sind DUMMIES** — finale Werte kommen von G1 (Sensorik), noch ausstehend.
  Beim Feature-Bau: **keine Hardcodierung**, alle Schwellen über `config/` austauschbar halten.
- Funktionale Vorgehensweise: **vom Kernpfad (T0) ausgehen**, Features als T1–T3 aufsetzen (s. `Backend-Konzept.md` / `Tasks+Projektplan.md`).
- Abweichungen vom Plan als **[DEVIATION]** markieren und begründen.

---

## 8. Teststrategie

- **Entscheidungslogik:** gegen die zwei dokumentierten Vorfälle (−2,1 °C → kein Eis, +1,2 °C → Eis) prüfen; Coverage ≥ 80 %.
- **Plausibilität/Ausfall:** Stale-/Defekt-Erkennung und Fail-safe (Ausfall → nie GRÜN) testen.
- **Systemtests:** End-to-End Sensor → Backend → Frontend.
- **Mensch-Maschine:** verifizieren, dass **keine** automatische Freigabe möglich ist (RB-01).
- Abnahme-Checkliste s. `Schwellenwerte.md` §3.

---

## 9. Sicherheits-Betrachtungen

- **Keine automatische Freigabe der Startbahn** — Mensch ist letzte Instanz (RB-01).
- **Redundanz/Ausfallabsicherung:** Sensoren werden beschädigt → Wartbarkeit/Ersatz.
- **Robustheit gegen Fehlinformationen:** falsche Daten, Komm./Stromausfall erkennen und behandeln.
- **Fehlalarm vs. Auslassung** bewusst austarieren (parametrierbar, K1).
- **Lokal vs. Cloud:** offen; bei Fernzugriff Authentifizierung/Autorisierung/Verschlüsselung (NF-07).

---

## 10. Meilensteine & Pflichtdokumente

| Meilenstein | Zeitpunkt | Zentrale Deliverables |
|---|---|---|
| M1 | Ende Woche 1 | Stakeholder-/Nutzermodell, erste Anforderungen, Schwellenwerte, Backend-Konzept, dokumentierte Konflikte |
| M2 | Ende Woche 2 | Funktionierende Teilmodule, **API & Datenmodell final**, erste Integration, Testprotokolle |
| M3 | Ende Woche 3 | Vollständiger Prototyp, Live-Demo, Abschlusspräsentation, Reflexion |

**Pflichtdokumente** (laut `Prüfungsleistung Anforderungen.txt`): Stakeholderanalyse, Lastenheft, Systemkontext,
Sensorstudie/-auswahl/Messkonzept (G1), **Datenmodell, API-Dokumentation, Vereisungslogik (G2)**,
UI-/Alarm-/Integrationskonzept (G3), Entscheidungslogbuch (laufend), Testprotokoll, Abschlusspräsentation.

---

## 11. Hinweise für Agenten

- **Scope respektieren:** G2 = Backend. Sensorik/Frontend **nicht** mitkonzipieren — nur die API-Schnittstelle definieren.
- **API-/Datenmodell-Vertrag beachten (Mandatory Read):** Vor jeder Arbeit an der G1→G2-Naht
  `Backend-Konzept.md` §9 lesen. Der Contract definiert `GET /current` (Snapshot + Pflichtfeld
  `measured_at`), `GET /health` (`200`/`503`) und die nicht verhandelbaren Pflichtfelder.
- **Anforderungs-/Konzeptdokumente beachten:** `Usecase-quick.md`, `Schwellenwerte.md`, `Backend-Konzept.md`
  (§9 API-Vertrag), `Tasks+Projektplan.md`, `teamstruktur-final.md` (gemeinsame IDs FA/NF/RB/AE/K, Tasks P#.#).
- **Belegbasiert arbeiten:** keine erfundenen Schwellenwerte/Quellen; Unsicheres kennzeichnen; bei Bedarf nachfragen.
- **⚠️ DUMMY-SCHWELLEN beachten:** Alle Zahlenwerte in `Schwellenwerte.md` sind aktuell **Platzhalterwerte**.
  Die verbindlichen Grenzwerte werden noch von **Gruppe 1 (Sensorik & Daten)** nachgeliefert.
  Beim Implementieren von Features und Tests gilt: **Schwellen nie hardcoden — immer über `config/`
  parametrierbar**, damit G1-Finalwerte ohne Code-Änderungen einspielbar sind.
- **Session-Recap:** Claude Code → `/ck:resume`; Kimi → aktuellste `recap_YYYY-MM-DD.md` unter `C:\Users\LucasVöhringer\.kimi\.recap\`.
- **Deutsch verwenden.** Sicherheitskritisches Ingenieursprojekt, kein normales Webprojekt.
- Abweichungen als **[DEVIATION]** markieren und begründen.
