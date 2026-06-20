# Alarmsystem-Dev · Backend & Entscheidungslogik Vereisungserkennung ANR

> **Arbeitsrepository der Backend-Gruppe (G2)** für den Projektkurs „Vereisungserkennung am Flughafen ANR".  
> Prototypisches System zur **Erfassung, Bewertung und Alarmierung von Vereisungsbedingungen**.

---

## Überblick

Dieses Repository enthält:

- **Briefing-Material** (Aufgabenstellung, Hintergrundgeschichte, Vorfälle) → `01-quellen/`
- **Erarbeitete Deliverables** (Requirements, Design, Projektplan) → `02-Arbeitsdokumente/`
- **Eingefrorene Abgaben** → `03-abgaben/`
- **Projektgedächtnis** (aktueller Stand, wird von `/start` gelesen) → `erinnerung/`
- **Backend-Code** → noch nicht implementiert (Phase P0–P2 steht an)

**Remote:** GitHub-Org `Entwicklerteam-WI2-0` · **Branch:** `main` (PR-Workflow, kein direkter Push)

> **Agenten-/Tooling-Setup wohnt getrennt:** Die KI-Werkzeuge (Skills, Hooks, geteilte Agent-Config)
> leben im separaten Stack `Devteam-vibecodes`. Dieses Repo ist für **Produktcode + Pflichtdokumentation**.
> `.claude/` im Root enthält nur das Minimum für das Team-Arbeiten (Commands `/setup`, `/start`).

---

## Repo-Struktur (aktueller Stand)

```
Alarmsystem-Dev/
├── 01-quellen/                              # Read-only Briefing-Material (vom Dozenten)
│   ├── Studierenden-Handreichung.txt        # Aufgabenstellung, Rollen, Bewertung
│   ├── Die Hintergrundgeschichte.txt        # Quellenmaterial (E-Mails, Protokolle, Vorfälle)
│   ├── Zeitplan.txt                         # 3-Wochen-Zeitplan M1–M3
│   └── Prüfungsleistung Anforderungen.txt   # Bewertungskriterien
│
├── 02-Arbeitsdokumente/                     # Lebende Deliverables (werden laufend gepflegt)
│   ├── Usecase-quick.md                     # FA-01–12, NF-01–11, RB-01, AE-01/02, K1–K9
│   ├── Schwellenwerte.md                    # Vereisungslogik + 4 Stufen (🟢🟡🟠🔴)
│   ├── Backend-Konzept.md                   # Architektur G2, Module, Datenmodell, Stack-Optionen
│   ├── Tasks+Projektplan.md                 # Phasen P0–P6, Meilensteine M1–M3, Kanban-Tasks
│   ├── Team-Organisation+Regeln.md          # Rollen/DRI, Git-Workflow, Teamregeln
│   ├── Entscheidungslog-Lucas-Systemarchitektur.md  # Pflicht-Deliverable (E-01–E-27)
│   ├── Raspberry-Pi-Hosting-Anleitung.md   # Pi als Backend-Host einrichten
│   └── assets/                              # Bilder (Architekturskizzen, Gruppeneinteilung)
│
├── 03-abgaben/                              # Abgabefertige, eingefrorene Stände
│   ├── Nutzer und Stakeholdermodel 1.md
│   └── Nutzer und Stakeholdermodel 2.md
│
├── erinnerung/                              # Geteiltes Projektgedächtnis (/start liest es)
│   ├── README.md                            # Verwendungshinweise
│   └── stand.md                            # Aktueller Stand, nächste Schritte, Blocker
│
├── .github/workflows/                       # GitHub Actions (KI-gestützte Code-Reviews)
│   ├── claude.yml                           # Claude-Bot für Issue-/PR-Kommentare
│   └── claude-code-review.yml              # Automatisches Code-Review bei PRs
│
├── .claude/                                 # Geteilte Claude-Code-Config (committet)
│   ├── commands/
│   │   ├── setup.md                         # /setup — Einmal-Einrichtung der Umgebung
│   │   └── start.md                         # /start — Kontext beim Sitzungsstart laden
│   └── hooks/
│       └── README.md
│
├── Agents-gpt-gemini.md                     # KI-Onboarding für ChatGPT/Gemini
├── claude-sync.md                           # Geteilte Agent-Config (Sync-Quelle für CLAUDE.md)
├── Gruppeneinteilung.png                    # Gruppeneinteilung (Bild)
├── CLAUDE.md                                # Persönliche Agent-Config (gitignored)
├── AGENTS.md                                # Agent-Onboarding (gitignored)
├── README.md                                # Diese Datei
└── .gitignore

```

> **Noch nicht im Repo (geplant, Phasen P0–P2):**
> `src/` (Backend-Code), `tests/` (Pytest), `config/thresholds.json`, `pyproject.toml` (uv/FastAPI).
> Geplante Struktur in `Backend-Konzept.md §7`.

---

## Kernauftrag & Scope (G2)

**G2 baut:**
- Daten-**Ingest** (REST `POST /readings` von Sensorik)
- **Datenhaltung** (SQLite → PostgreSQL)
- **Vereisungsbewertung** (4-Stufen-Logik: 🟢🟡🟠🔴)
- **Alarm-Generierung** (Schweregrad, Hysterese)
- **Prognose** (30-min-Vorlauf)
- **API** (Serving für Frontend, Abfragen, Konfiguration)
- **Logging/Audit** (append-only, Compliance)

**G2 baut NICHT:**
- Sensor-Hardware/Messung → **Gruppe 1** (G2 definiert nur das Format)
- Visualisierung/UI → **Gruppe 3** (G2 liefert die Daten via API)

**Die Naht = API + Datenmodell** — das ist das kritische Interface zwischen allen drei Gruppen.

---

## Datenfluss (Backend)

```
  (von G1 — Sensoren)
         ↓
    POST /readings
         ↓
   ┌─────────────────────────────────────────┐
   │    Eingangsvalidierung & Plausibilität   │
   │  (Bereich, Stale, Sensor-Defekt)        │
   └─────────────────────────────────────────┘
         ↓
   ┌─────────────────────────────────────────┐
   │   Persistenz (DB: readings)              │
   └─────────────────────────────────────────┘
         ↓
   ┌──────────────────────────────────────────┐
   │  Bewertungsmodul (4-Stufen-Logik)        │
   │  Input: T_s, T_d, RH, Niederschlag      │
   │  Output: risk_level (green/yellow/...)  │
   └─────────────────────────────────────────┘
         ↓
   ┌─────────────────────────────────────────┐
   │   Alarm-Generierung (falls Schwelle)    │
   └─────────────────────────────────────────┘
         ↓
   ┌─────────────────────────────────────────┐
   │   Audit-Log (append-only Event-Trail)   │
   └─────────────────────────────────────────┘
         ↓
   ┌─────────────────────────────────────────┐
   │  API-Serving: GET /assessment/current   │
   │             GET /alarms                 │
   │             GET /readings?from&to       │
   └─────────────────────────────────────────┘
         ↓
    (an G3 — Frontend)
```

---

## Vereisungslogik (4 Stufen)

Definiert in **`02-Arbeitsdokumente/Schwellenwerte.md §2`**:

| Stufe | Bedingung | Bedeutung |
|---|---|---|
| 🟢 **GRÜN** | `T_s > +1,0 °C` | Kein Vereisungsrisiko |
| 🟡 **GELB** | `T_s ≤ +1,0 °C` + trocken / OR Prognose `T_s ≤ 0 °C` in ≤ 30 min | Beobachtung + Vorwarnung |
| 🟠 **ORANGE** | `T_s ≤ 0,0 °C` + Feuchte vorhanden | Vereisung wahrscheinlich → Warnung |
| 🔴 **ROT** | `T_s ≤ 0,0 °C` + (gefrierender Regen OR `ΔT ≤ 0 °C`) | **Aktive Eisbildung** → Alarm + Quittierung |

**Beide dokumentierten Vorfälle korrekt aufgelöst:**
- Vorfall 1 (−2,1 °C Luft, trocken): → **GELB** (kein Fehlalarm)
- Vorfall 2 (+1,2 °C Luft, Oberfläche < 0 °C): → **ORANGE/ROT** (Vereisung erkannt)

---

## Wichtige Deliverables

### Anforderungen (FA/NF/RB)
**Datei:** `02-Arbeitsdokumente/Usecase-quick.md`  
FA-01–12 (Temperatur/Feuchte/Messung/Alarmierung/Logging), NF-01–11 (Zuverlässigkeit, Latenz, Wartbarkeit),
RB-01 (Mensch ist letzte Instanz — **keine automatischen Freigaben**), offene Entscheidungen AE-01/02,
Konfliktanalyse K1–K9.

### Schwellenwerte & Kalibriervorgaben
**Datei:** `02-Arbeitsdokumente/Schwellenwerte.md`  
4-Stufen-Logik (§2), Mess-Schwellen je Größe, Entprellung/Hysterese, Parameter je FA/NF.
Alle Werte sind **parametrierbar** (keine Hardcodes).

### Backend-Architektur
**Datei:** `02-Arbeitsdokumente/Backend-Konzept.md`  
Module (Ingest, Validierung, Persistenz, Bewertung, Alarm, Prognose, API, Config, Audit),
Datenmodell (6 Tabellen), Tech-Stack-Optionen (T0: FastAPI + SQLite + HTTP), Ausbaustufen T0–T3,
Schnittstellen zu G1/G3.

### Projektplan & Kanban
**Datei:** `02-Arbeitsdokumente/Tasks+Projektplan.md`  
Phasen P0–P6 (Setup → Contract → T0 Slice → T1 Kern → T2 Betrieb → Integration → T3 Erweiterung),
Meilensteine M1–M3, Tasks mit Owner/DoD/Größe.

### Entscheidungslogbuch
**Datei:** `02-Arbeitsdokumente/Entscheidungslog-Lucas-Systemarchitektur.md`  
E-01–E-27: alle getroffenen Architektur- und Organisationsentscheidungen mit Begründung und
verworfenen Alternativen. Pflicht-Deliverable.

### Raspberry Pi als Backend-Host
**Datei:** `02-Arbeitsdokumente/Raspberry-Pi-Hosting-Anleitung.md`  
Schritt-für-Schritt-Anleitung: Pi einrichten, SSH-Zugriff, VS Code Remote-SSH, Backend deployen.
Löst AE-01 (lokal vs. Cloud) zugunsten eines lokalen Pi-Hosts auf.

### Team-Organisation & Rollen
**Datei:** `02-Arbeitsdokumente/Team-Organisation+Regeln.md`  
Rollenverteilung (DRI-Prinzip), Zusammenarbeits-Map, Git-Workflow, Definition of Ready/Done, Cadence.

---

## Tech-Stack (T0 — Empfehlung, finale Wahl im Entscheidungslogbuch)

| Komponente | Empfehlung T0 | Alternativen |
|---|---|---|
| **Sprache** | Python 3.11+ | — |
| **Framework** | FastAPI | Flask, Node/Express |
| **Validierung** | Pydantic v2 | — |
| **Datenbank** | SQLite (T0) → PostgreSQL (T1+) | TimescaleDB |
| **Übertragung** | HTTP REST (`POST /readings`) | MQTT (später) |
| **Testing** | pytest + coverage | unittest |
| **Logging** | Python `logging` + structlog | — |
| **Hosting** | Raspberry Pi (lokal, SSH) | Cloud-VM |

Stack-Wahl **begründen** im Entscheidungslogbuch; Team-Kompetenz ist entscheidend.

---

## Schnelleinstieg für Entwickler

### 1. Repository klonen
```bash
git clone https://github.com/Entwicklerteam-WI2-0/Alarmsystem-Dev.git
cd Alarmsystem-Dev
```

### 2. Arbeitsdokumente lesen (WICHTIG — vor dem ersten Commit)
```
1. 02-Arbeitsdokumente/Backend-Konzept.md           # Was bauen wir?
2. 02-Arbeitsdokumente/Schwellenwerte.md             # Wie entscheidet die Logik?
3. 02-Arbeitsdokumente/Usecase-quick.md              # Welche Anforderungen?
4. 02-Arbeitsdokumente/Tasks+Projektplan.md          # Wer macht was bis wann?
5. 02-Arbeitsdokumente/Team-Organisation+Regeln.md   # Wie arbeiten wir zusammen?
```

### 3. Umgebung einrichten (sobald P0 abgeschlossen)

> P0 ist noch nicht abgeschlossen — `src/`, `tests/`, `pyproject.toml` existieren noch nicht.
> Sobald P0.2/P0.3 durch sind, erscheint hier die Installationsanleitung.

Voraussichtlich:
```bash
uv sync          # Python-Umgebung aus pyproject.toml (sobald vorhanden)
uv run python src/main.py   # Server starten (T0-Ziel: GET /health → 200)
uv run pytest tests/ -v --cov=src   # Tests (≥ 80 % Coverage Ziel)
```

### 4. Feature-Branch erstellen & PR öffnen
```bash
git checkout -b feature/P0-setup
# ... Code schreiben ...
git commit -m "[P0.2] Repo-Grundstruktur anlegen"
git push origin feature/P0-setup
# → Pull Request auf main öffnen (Review durch Systemarchitekt)
```

---

## Git-Workflow & Regeln

### Branches
- **`main`** — muss immer sauber sein (kein direkter Push, nur via PR)
- **Feature-Branches:** `feature/P0-setup`, `feature/P2-assessment`, etc.
- **Bugfix:** `bugfix/stale-detection`, etc.
- **Naming:** `[epic]/[task-id]-[kurzbeschreibung]`

### Commits
```
[P2.4] Bewertungsmodul: 4-Stufen-Logik + Hysterese

- Implementiere Magnus-Taupunkt-Berechnung
- Schwellenwerte aus Schwellenwerte.md §2 parametrisierbar
- Unit-Tests: beide Vorfälle validiert

Refs: FA-05, NF-01, Schwellenwerte.md
```

### Pull Requests
1. **Titel:** `[Phase] Kurzbeschreibung`
2. **Description:** Was, warum, wie; Links zu Docs
3. **Review:** Systemarchitekt (Lucas V.) bestätigt Contract
4. **Tests:** mindestens grün vor Merge
5. **Merge:** Squash oder Rebase

---

## Zusammenarbeit mit anderen Gruppen

**Systemarchitekt (Lucas V. + Johannes P.) = DRI für beide Schnittstellen.**

| Gruppe | Schnittstelle | Status |
|---|---|---|
| **G1 (Sensorik)** | `POST /readings` — Payload, Felder, Einheiten, Frequenz | Seam-Sync steht an (Anfang Wo 2) |
| **G3 (Frontend)** | `GET /assessment/current`, `GET /alarms` — Response-Format | Seam-Sync steht an (Anfang Wo 2) |

**Die API/das Datenmodell ist die einzige Naht** — Contract-first einfrieren, dann kann G1 und G3 parallel entwickeln. Details: `Backend-Konzept.md §9`.

---

## Kritischer Pfad & Risiken

### Engpässe
1. **API/Datenmodell-Contract (P1)** — verzögert G1 + G3 gleichzeitig
2. **Bewertungslogik (P2.4)** — Kernmodul, hohe Testanforderung
3. **Stack-Entscheidung (P0.1)** — muss zuerst fallen, alles andere hängt dran

### Mitigation
- Contract-first (P1) auf verlässlichste Köpfe: Architekt + 1–2 Backend-Devs
- Contract früh einfrieren (Mitte Woche 1)
- Parallel gegen denselben Contract entwickeln
- Seam-Syncs mit G1/G3 regelmäßig halten

---

## Kontakt & Rollen

| Rolle | Person | Verantwortung |
|---|---|---|
| Teilprojektleiter | Landmann, Lucas | Scope, Blocker, Außenkontakt |
| **Systemarchitekt** | **Vöhringer, Lucas** + Petzold, Johannes | API, Datenmodell, Schnittstellen |
| Backend-Devs | Hartling, Leon · Ganter, Luca · Moritz, Andreas · Sarkhab, Arash | Ingest, Persistenz, Bewertungslogik, API |
| Test / Review | Mohammadi, Azezoo · Berger, Amelie | Definition of Done, Testprotokoll |
| Dokumentation | Reisi, Maryam + Ilchyshyn, Vladyslav | Entscheidungslogbuch, API-Doku |

**Fragen zur Architektur?** → Lucas V. (Systemarchitekt)  
**Fragen zum Task-Status?** → `erinnerung/stand.md` + Standup 2–3×/Woche

---

## Meilensteine (3 Wochen)

| Meilenstein | Ziel | Deadline |
|---|---|---|
| **M1** | Setup (P0) + Contract v1 API/Datenmodell (P1) | Ende Woche 1 |
| **M2** | T0 Vertical Slice (P2) + T1 Kernfunktion (P3) | Ende Woche 2 |
| **M3** | T2 Betrieb (P4) + Integration + E2E-Test + Präsentation (P5) | Ende Woche 3 |

Stretch: **T3** (Prognose, Multi-Sensor, Fernwartung) falls Zeit (P6).

---

## Weiterführende Ressourcen

- **Briefing:** `01-quellen/Die Hintergrundgeschichte.txt` — absichtlich unvollständiges Rohmaterial
- **KI-Onboarding:** `Agents-gpt-gemini.md` — Briefing für ChatGPT/Gemini
- **Aktueller Stand:** `erinnerung/stand.md` — Snapshot für den Sitzungsstart
- **GitHub-Org:** https://github.com/Entwicklerteam-WI2-0

---

*Letzte Aktualisierung: 20.06.2026 — G2 Backend & Entscheidungslogik*
