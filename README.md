# Alarmsystem-Dev · Backend & Entscheidungslogik Vereisungserkennung ANR

> **Arbeitsrepository der Backend-Gruppe (G2)** für den Projektkurs „Vereisungserkennung am Flughafen ANR".  
> Prototypisches System zur **Erfassung, Bewertung und Alarmierung von Vereisungsbedingungen**.

---

## 📋 Überblick

Dieses Repository enthält:

- **Briefing-Material** (Aufgabenstellung, Hintergrundgeschichte, Vorfälle) → `01-quellen/`
- **Erarbeitete Deliverables** (Requirements, Design, Projektplan) → `02-Arbeitsdokumente/`
- **Backend-Code** (geplant) → `src/`, `tests/`
- **Entscheidungslogbuch** (KI-Onboarding, Agenten-Briefe) → Root

**Remote:** GitHub-Org `Entwicklerteam-WI2-0` · **Branch:** `main` (geschützt)  
**Lokaler Pfad (Team-Dev):** `C:\Users\LucasVöhringer\Desktop\Alarmsystem-Dev`

---

## 🏗️ Repo-Struktur

```
Alarmsystem-Dev/
├── 01-quellen/                          # Read-only Briefing-Material
│   ├── Studierenden-Handreichung.txt    # Aufgabenstellung, Rollen, Bewertung
│   ├── Die Hintergrundgeschichte.txt    # Quellenmaterial (E-Mails, Protokolle, Vorfälle)
│   ├── Zeitplan.txt                     # 3-Wochen-Zeitplan M1–M3
│   └── Prüfungsleistung Anforderungen.txt
│
├── 02-Arbeitsdokumente/                 # Lebende Deliverables (gepflegt)
│   ├── Usecase-quick.md                 # FA-01–12, NF-01–11, RB-01, AE-01/02, Konfliktanalyse K1–K9
│   ├── Schwellenwerte.md                # Vereisungslogik + 4 Stufen (🟢🟡🟠🔴) + Kalibriervorgaben
│   ├── Backend-Konzept.md               # Architektur G2, Module, Datenmodell, Tech-Stack-Optionen
│   ├── Projektplan-Backend.md           # Phasen P0–P6, Meilensteine M1–M3, Kanban-Tasks
│   ├── Team-Organisation+Regeln.md      # Rollen/DRI, Zusammenarbeits-Map, Teamregeln
│   └── assets/                          # Bilder (Architekturskizzen, Rollen, Gruppen)
│
├── 03-abgaben/                          # Abgabefertige, eingefrorene Stände
│   ├── Nutzer und Stakeholdermodel 1.md
│   └── Nutzer und Stakeholdermodel 2.md
│
├── src/                                 # Backend-Code (in Arbeit)
│   ├── ingest/                          # REST-Endpoint, Eingangsvalidierung
│   ├── model/                           # Datenklassen/Schemas (Pydantic)
│   ├── assessment/                      # Vereisungslogik (Schwellenwerte) — Kernmodul
│   ├── storage/                         # DB-Zugriff (Repository-Pattern)
│   ├── api/                             # API-Endpoints für G3 (Frontend)
│   ├── config/                          # Schwellen/Parametrierung
│   ├── forecast/                        # 30-min-Prognose (T3)
│   └── main.py                          # Einstiegspunkt (FastAPI)
│
├── tests/                               # Unit/Integrationstests
│   ├── test_assessment.py               # Bewertungslogik (Kernmodule, ≥ 80 % Coverage)
│   ├── test_ingest.py                   # Validierung + Plausibilität
│   ├── test_api.py                      # API-Schnittstellen
│   └── test_integration_e2e.py          # End-to-End (mit G1/G3)
│
├── config/                              # Default-Schwellenwerte (parametrierbar)
│   └── thresholds.json
│
├── .github/workflows/                   # CI/CD (geplant)
│   ├── test.yml
│   └── deploy.yml
│
├── .claude/                             # Geteilte Claude-Code-Config (committet)
│   ├── settings.json                    # Hooks (SessionStart; Enforcement folgt in Phase 2)
│   ├── commands/                        # /setup, /start
│   └── hooks/                           # Standalone-Hook-Skripte (Phase 2)
├── erinnerung/                          # Geteiltes Projektgedächtnis (/start liest es)
│   ├── README.md
│   └── stand.md
├── setup.sh  /  setup.ps1               # Einmal-Setup (macOS / Windows)
├── pyproject.toml                       # uv-Umgebung (FastAPI, pytest, ruff)
├── claude-sync.md                       # Geteilte Agent-Config → wird lokal zu CLAUDE.md
├── ONBOARDING.md                        # 3-Schritt-Schnellstart
├── CLAUDE.md                            # Persönliche Agent-Config (gitignored; lokal aus claude-sync.md)
├── AGENTS.md                            # Agent-Onboarding (gitignored)
├── Agents-gpt-gemini.md                 # KI-Onboarding für ChatGPT/Gemini
├── README.md                            # Diese Datei
└── .gitignore

```

---

## ⚙️ Setup & Onboarding (in 3 Schritten)

> Vom blanken Rechner zur fertig konfigurierten Agenten-Umgebung — **ohne** manuelles Gefummel.
> Funktioniert auf **macOS** und **Windows**. Ausführlich: [`ONBOARDING.md`](ONBOARDING.md).

**1. Claude Code installieren** (einmalig) — offizielle CLI. Test: `claude --version`.

**2. Repo klonen**
```bash
git clone https://github.com/Entwicklerteam-WI2-0/Alarmsystem-Dev.git
cd Alarmsystem-Dev
```

**3. Setup-Skript ausführen**
```bash
bash setup.sh                                        # macOS / Linux
powershell -ExecutionPolicy Bypass -File setup.ps1   # Windows
```
Installiert `uv` (falls nötig), baut die Python-Umgebung (`uv sync`) und legt deine lokale `CLAUDE.md` aus `claude-sync.md` an.

**Danach arbeiten:** Ordner in **VS Code** öffnen → im Terminal **`claude`** starten → einmal **„Projekt vertrauen"** → **`/start`** tippen (lädt Kontext, Stand & Regeln).

### Was das Repo automatisch mitbringt
- **Skills/Commands** (`/setup`, `/start`, …) und **Standard-Checks** (Hooks) — direkt aus `.claude/`, keine Einzelkonfiguration nötig.
- **Identische Python-Umgebung** für alle via `uv` + `pyproject.toml`.
- **Geteiltes Gedächtnis** in `erinnerung/` (wird von `/start` gelesen).
- **Gemeinsame Regeln** in `claude-sync.md` → lokal als `CLAUDE.md`.

> Gemeinsame Regeln immer in **`claude-sync.md`** ändern (per PR) — **nicht** in der lokalen `CLAUDE.md`, sonst driften die Stände auseinander.

---

## 🎯 Kernauftrag & Scope (G2)

**G2 baut:**
- Daten-**Ingest** (REST `POST /readings` von Sensorik)
- **Datenhaltung** (SQLite/PostgreSQL)
- **Vereisungsbewertung** (4-Stufen-Logik: 🟢🟡🟠🔴)
- **Alarm-Generierung** (Schweregrad, Hysterese)
- **Prognose** (30-min-Vorlauf)
- **API** (Serving für Frontend, Abfragen, Konfiguration)
- **Logging/Audit** (append-only, Compliance)

**G2 baut NICHT:**
- Sensor-Hardware/Messung → **Gruppe 1** (G2 definiert Format)
- Visualisierung/UI → **Gruppe 3** (G2 liefert Daten)

**Die Naht = API + Datenmodell** — das ist das kritische Interface.

---

## 📊 Datenfluss (Backend)

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
   ┌───────────────────────────────────��─────┐
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

## 🔑 Entscheidungskategorien (Vereisungslogik)

Definiert in **`02-Arbeitsdokumente/Schwellenwerte.md §2`**:

| Stufe | Bedingung | Bedeutung |
|---|---|---|
| 🟢 **GRÜN** | `T_s > +1,0 °C` | Kein Vereisungsrisiko |
| 🟡 **GELB** | `T_s ≤ +1,0 °C` + trocken / OR Prognose `T_s ≤ 0 °C` in ≤ 30 min | Beobachtung + Vorwarnung |
| 🟠 **ORANGE** | `T_s ≤ 0,0 °C` + Feuchte vorhanden | Vereisung wahrscheinlich → Warnung |
| 🔴 **ROT** | `T_s ≤ 0,0 °C` + (gefrierender Regen OR `ΔT ≤ 0 °C`) | **Aktive Eisbildung** → Alarm + Quittierung |

**Beide dokumentierten Vorfälle gelöst:**
- Vorfall 1 (−2,1 °C Luft, trocken): **GELB** (kein Fehlalarm)
- Vorfall 2 (+1,2 °C Luft, Oberfläche < 0 °C): **ORANGE/ROT** (Vereisung erkannt)

---

## 📑 Wichtige Deliverables

### Funktionale & Nicht-Funktionale Anforderungen
**Datei:** `02-Arbeitsdokumente/Usecase-quick.md`  
**Inhalt:** FA-01–12 (z. B. Temperatur-/Feuchte-/Niederschlagmessung, Alarmierung, Logging)  
**+ NF-01–11** (Zuverlässigkeit, Latenz, Wartbarkeit, Security, Verfügbarkeit)  
**+ RB-01:** Harte Randbedingung: Mensch ist letzte Instanz — **keine automatischen Freigaben**.

### Schwellenwerte & Kalibriervorgaben
**Datei:** `02-Arbeitsdokumente/Schwellenwerte.md`  
**Inhalt:**
- 4-Stufen-Logik (§2) — die Kernentscheidungslogik
- Mess-Schwellen je Größe (T_s ±0,3 °C, RH ±3 %, etc.) — Vorgabe für Sensorik (G1)
- Entprellung/Hysterese gegen Chattering
- Parameter je FA/NF
- **Startwerte (alles parametrierbar)** — keine Hardcodes

### Backend-Architektur & Code-Struktur
**Datei:** `02-Arbeitsdokumente/Backend-Konzept.md`  
**Inhalt:**
- Module (Ingest, Validierung, Persistenz, Bewertung, Alarm, Prognose, API, Config, Audit)
- Datenmodell (Tabellen: `reading`, `assessment`, `alarm`, `acknowledgement`, `threshold_set`, `audit_log`)
- Tech-Stack-Optionen (FastAPI + Pydantic, SQLite → PostgreSQL, HTTP-POST)
- Ausbaustufen T0–T3
- Schnittstellen zu G1 (Sensorik) & G3 (Frontend)

### Projektplan & Kanban
**Datei:** `02-Arbeitsdokumente/Projektplan-Backend.md`  
**Inhalt:**
- Phasen **P0–P6** (Setup → Contract → T0 Slice → T1 Kern → T2 Betrieb → Integration → T3 Erweiterung)
- Meilensteine **M1–M3** (Wochenenden 1, 2, 3)
- **Tasks mit Owner, DoD, Größe** — Kanban-Ready
- Definition of Done (4 Punkte: PR/Review/Tests/Entscheidungslogbuch)

### Team-Organisation & Rollen
**Datei:** `02-Arbeitsdokumente/Team-Organisation+Regeln.md`  
**Inhalt:**
- Rollenverteilung (Teilprojektleiter, Systemarchitekt, Backend-Entwickler, Test, Dokumentation)
- **DRI-Prinzip** (ein Owner pro Task, keine Komitees)
- Zusammenarbeits-Map (engste Kopplungen: Architekt ⇄ Devs, Architekt ⇄ G1/G3)
- Git-Workflow (Feature-Branch → PR → Review → Merge)
- Definition of Ready/Done
- Cadence (Standup 2–3×/Woche, Seam-Sync 1×/Woche)

---

## 🛠️ Tech-Stack (T0)

| Komponente | Empfehlung | Alternativen |
|---|---|---|
| **Sprache** | Python 3.9+ | — |
| **Framework** | FastAPI | Flask, Node/Express |
| **Validierung** | Pydantic v2 | — |
| **Datenbank** | SQLite (T0) → PostgreSQL (T1+) | TimescaleDB |
| **Übertragung** | HTTP REST (`POST /readings`) | MQTT (später) |
| **Testing** | pytest + coverage | unittest |
| **Logging** | Python `logging` + structlog | — |

**Auswahl begründen** im Entscheidungslogbuch (Team-Kompetenz, Prototyp-Fokus).

---

## 🚀 Schnelleinstieg für Entwickler

### 1. Repository klonen
```bash
git clone https://github.com/Entwicklerteam-WI2-0/Alarmsystem-Dev.git
cd Alarmsystem-Dev
```

### 2. Arbeitsdokumente lesen (WICHTIG)
```bash
# Reihenfolge für Einstieg:
1. 02-Arbeitsdokumente/Backend-Konzept.md          # Was bauen wir?
2. 02-Arbeitsdokumente/Schwellenwerte.md          # Wie entscheidet die Logik?
3. 02-Arbeitsdokumente/Usecase-quick.md           # Welche Anforderungen?
4. 02-Arbeitsdokumente/Projektplan-Backend.md    # Wer macht was bis wann?
5. 02-Arbeitsdokumente/Team-Organisation+Regeln.md # Wie arbeiten wir zusammen?
```

### 3. Umgebung aufsetzen
```bash
# Einmal-Setup übernimmt alles (uv, Python-Umgebung, lokale CLAUDE.md):
bash setup.sh                                        # macOS / Linux
powershell -ExecutionPolicy Bypass -File setup.ps1   # Windows
```
> Erstmaliges Onboarding: siehe **⚙️ Setup & Onboarding** oben. Manuell geht auch: `uv sync` (nutzt `pyproject.toml`).

### 4. Server starten
```bash
# T0-Ziel: GET /health → 200 OK
uv run python src/main.py
```

### 5. Tests schreiben & laufen
```bash
uv run pytest tests/ -v --cov=src --cov-report=html
# Bewertungslogik-Tests = Priorität 1 (≥ 80 % Coverage)
```

### 6. Feature-Branch erstellen & PR öffnen
```bash
git checkout -b feature/FA-XY-beschreibung
# ... Code schreiben ...
git commit -m "[P1.2] Bewertungsmodul implementiert — FA-05"
git push origin feature/FA-XY-beschreibung
# → Pull Request auf main (gegen Architekten-Review)
```

---

## 📋 Git-Workflow & Regeln

### Branches
- **`main`** — produktiv, muss immer lauffähig sein (geschützt)
- **Feature-Branches:** `feature/P0-setup`, `feature/P2-assessment`, etc.
- **Bugfix:** `bugfix/stale-detection`, etc.
- **Naming:** `[epic]/[task-id]-[kurzbeschreibung]`

### Commits
```
[P1.2] Bewertungsmodul: 4-Stufen-Logik + Hysterese

- Implementiere Magnus-Taupunkt-Berechnung
- Schwellenwerte aus Schwellenwerte.md §2 parametrisierbar
- Unit-Tests: beide Vorfälle validiert
- Entscheidung: Separate assessment-Funktion (testbar)

Refs: FA-05, NF-01, Schwellenwerte.md
```

### Pull Requests
1. **Titel:** `[Phase/Epic] Kurzbe schreibung`
2. **Description:** Was, warum, wie; Links zu Docs
3. **Review:** Architekt (Lucas V.) bestätigt Contract
4. **Tests:** mindestens grün vor Merge
5. **Merge:** Squash oder Rebase (kein Clutter)

---

## 📐 Interne Conventions

### Code-Struktur (`src/`)
```
assessment/
├── __init__.py
├── logic.py           # Pure functions (testbar): assess(reading, threshold_set) → assessment
├── thresholds.py      # Threshold-Klasse + default values
└── validator.py       # Plausibilitäts-Checks

model/
├── __init__.py
├── schemas.py         # Pydantic-Modelle (Request/Response)
└── entities.py        # DB-Entitäten
```

### Tests
```
tests/
├── test_assessment.py       # Unit: Bewertungslogik
├── test_ingest.py           # Unit: Validierung
├── test_api.py              # Unit: Endpoints
└── test_integration_e2e.py  # Integration: Full-Stack
```

### Naming
- **Python:** `snake_case` (Funktionen, Variablen)
- **Klassen:** `PascalCase`
- **Konstanten:** `UPPER_SNAKE_CASE`
- **DB-Spalten:** `snake_case`

---

## 🤝 Zusammenarbeit mit anderen Gruppen

### Schnittstellen (die eine Naht)
**Systemarchitekt (Lucas V. + Johannes P.) = DRI für beide Seiten.**

#### zu G1 (Sensorik)
- **`POST /readings`-Payload** — welche Felder, welche Einheiten?
- **Update-Frequenz** — wie oft pushen?
- **Seam-Sync:** 1×/Woche (Anfang Woche 2)

#### zu G3 (Frontend)
- **`GET /assessment/current`-Response** — welche Felder, Formatierung?
- **`GET /alarms`** — wie werden Alarme visualisiert?
- **Seam-Sync:** 1×/Woche (Anfang Woche 2)

---

## 📚 Dokumentation & Entscheidungslogbuch

**Jede Entscheidung** (Tech-Stack, Schwellenwert-Anpassung, Architektur-Pivot) muss dokumentiert werden:

### Was dokumentieren?
- **Was:** Entscheidung selbst
- **Warum:** Kontext + Alternativen
- **Folgen:** Impact auf andere Tasks
- **Wer + Wann:** Owner + Datum

### Wo dokumentieren?
- **Technisch:** Root-Datei `Entscheidungslogbuch.md` (geplant) oder in PR-Beschreibungen
- **Prozess:** Doku-Rolle (Maryam + Vladyslav) sammelt regelmäßig ein

---

## ⚠️ Kritischer Pfad & Risiken

### Engpässe
1. **API/Datenmodell-Naht (P1)** — verzögert G1 + G3 gleichzeitig
2. **Bewertungslogik (P2.4)** — Kernmodul, hohe Test-Anforderung
3. **Sensorik-Kalibrierung (G1)** — ohne ±0,3 °C um 0 °C funktioniert nichts

### Mitigation
- **P1 auf stärkste Köpfe legen** (Architekt + 1–2 Backend-Devs)
- **Contract früh einfrieren** (Mitte Woche 1)
- **Parallel entwickeln** gegen denselben Vertrag
- **Seam-Syncs** regelmäßig halten

---

## 📞 Kontakt & Rollen

| Rolle | Person | Verantwortung |
|---|---|---|
| Teilprojektleiter | Landmann, Lucas | Scope, Blocker, Außenkontakt |
| **Systemarchitekt** | **Vöhringer, Lucas** + Petzold, Johannes | API, Datenmodell, Schnittstellen |
| **Backend-Lead** | **Vöhringer, Lucas** | Code-Quality, Reviews, Backend-Koordination |
| Backend-Devs | Hartling, Leon · Ganter, Luca · Moritz, Andreas · Sarkhab, Arash | Ingest, Persistenz, Bewertungslogik, API |
| Test-Lead | Mohammadi, Azezoo | Definition of Done, Testprotokoll |
| Dokumentation | Reisi, Maryam + Ilchyshyn, Vladyslav | Entscheidungslogbuch, API-Doku |

**Fragen zur Architektur?** → Lucas V.  
**Fragen zum Code?** → Leon H.  
**Fragen zum Status?** → Standup 2–3×/Woche

---

## 📖 Weiterführende Ressourcen

- **Briefing:** `01-quellen/Die Hintergrundgeschichte.txt` — unvollständiges Rohmaterial (absichtlich!)
- **KI-Onboarding:** `Agents-gpt-gemini.md` — für ChatGPT/Gemini/Claude
- **Claude-spezifisch:** `CLAUDE.md` (gitignored)
- **GitHub-Org:** https://github.com/Entwicklerteam-WI2-0

---

## 📅 Meilensteine (3 Wochen)

| Meilenstein | Ziel | Deadline |
|---|---|---|
| **M1** | Setup + Contract v1 (API/Datenmodell) | Ende Woche 1 |
| **M2** | T0 Vertical Slice + T1 Kernfunktion | Ende Woche 2 |
| **M3** | Integration + E2E-Test + Präsentation | Ende Woche 3 |

---

## 📝 Lizenz & Konventionen

- **Lizenz:** Projekt-Repo (ggf. später spezifizieren)
- **Sprache:** Deutsch (Docs), Englisch (Code-Kommentare, wo sinnvoll)
- **Timezone:** CET (UTC+1)

---

**Viel Erfolg bei der Implementierung!** 🚀

*Letzte Aktualisierung: 17.06.2026 — G2 Backend & Entscheidungslogik*
