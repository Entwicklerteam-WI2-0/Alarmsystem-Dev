# Alarmsystem-Dev · Backend & Entscheidungslogik Vereisungserkennung ANR

> **Arbeitsrepository der Backend-Gruppe (G2)** für den Projektkurs „Vereisungserkennung am Flughafen ANR".  
> Prototypisches System zur **Erfassung, Bewertung und Alarmierung von Vereisungsbedingungen**.

---

## 📋 Überblick

Dieses Repository enthält:

- **Briefing-Material** (Aufgabenstellung, Hintergrundgeschichte, Vorfälle) → `01-quellen/`
- **Erarbeitete Deliverables** (Requirements, Design, Projektplan) → `02-Arbeitsdokumente/`
- **Backend-Code** (FastAPI · MySQL/MariaDB · rohes PyMySQL, kein ORM → E-35) → `04-Source-code/`
- **Fortschrittslog** (Code-Stand + Commits/PRs) → `05-Fortschrittslog/`
- **Entscheidungslogbuch** → `02-Arbeitsdokumente/Entscheidungslog-Lucas-Systemarchitektur.md` · **KI-Onboarding** → Root (`Agents-gpt-gemini.md`)

**Remote:** GitHub-Org `Entwicklerteam-WI2-0` · **Branch:** `main` (PR-Workflow, kein direkter Push)  
**Lokaler Pfad:** lokal je Entwickler:in (kein fixer Team-Pfad)

> **🧰 Agenten-/Tooling-Setup wohnt jetzt getrennt:** Die kanonische Heimat der KI-Werkzeuge (Setup,
> geteilte Agent-Config, Onboarding, Skill-Pläne) ist der **Vibecoding-Stack** `Devteam-vibecodes` —
> *dort* wird das Werkzeug gepflegt, mit dem *hier* gebaut wird. Dieses Repo ist für **Produktcode +
> Pflichtdokumentation**. Noch vorhandene Setup-/Agenten-Dateien im Root sind eine Übergangs-Redundanz.

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
│   ├── Tasks+Projektplan.md           # Phasen P0–P6, Meilensteine M1–M3, Kanban-Tasks
│   ├── Team-Organisation+Regeln.md      # Rollen/DRI, Zusammenarbeits-Map, Teamregeln
│   └── assets/                          # Bilder (Architekturskizzen, Rollen, Gruppen)
│
├── 03-abgaben/                          # Abgabefertige, eingefrorene Stände
│   ├── Nutzer und Stakeholdermodel 1.md
│   └── Nutzer und Stakeholdermodel 2.md
│
├── 04-Source-code/                      # Backend-Code (P0-Grundgerüst steht)
│   ├── src/
│   │   ├── ingest/                      # Pull-Poller (GET /current bei G1), Eingangsvalidierung
│   │   ├── model/                       # Datenklassen/Schemas (Pydantic)
│   │   ├── assessment/                  # Vereisungslogik (Schwellenwerte) — Kernmodul, DB-frei
│   │   ├── storage/                     # DB-Zugriff (Repository-Pattern, rohes PyMySQL → MySQL/MariaDB; kein ORM, E-35)
│   │   ├── api/                         # API-Endpoints für G3 (Frontend)
│   │   ├── config/                      # Schwellen/Parametrierung
│   │   ├── forecast/                    # 30-min-Prognose (T3)
│   │   └── main.py                      # Einstiegspunkt (FastAPI), GET /v1/health
│   ├── tests/                           # Unit/Integrationstests
│   ├── migrations/                      # handgeschriebenes schema.sql (kein Alembic, E-35)
│   ├── config/                          # Default-Schwellenwerte (parametrierbar)
│   ├── .env.example                     # DB-Zugangsdaten (Platzhalter; keine Secrets)
│   ├── pyproject.toml · requirements*.txt
│   └── README.md                        # Setup + Struktur des Backends
│
├── 05-Fortschrittslog/                  # Code-Stand + Commit-/PR-Log (Orientierung)
│   └── Fortschrittslog.md
│
├── .github/workflows/                   # CI/CD (geplant)
│
├── .claude/                             # Geteilte Claude-Code-Config (committet)
│   ├── settings.json                    # Hooks (SessionStart; Enforcement folgt in Phase 2)
│   ├── commands/                        # /setup, /start
│   └── hooks/                           # Standalone-Hook-Skripte (Phase 2)
├── erinnerung/                          # Geteiltes Projektgedächtnis (/start liest es)
│   ├── README.md
│   └── stand.md
├── claude-sync.md                       # Geteilte Agent-Config → wird lokal zu CLAUDE.md
├── ONBOARDING.md                        # 3-Schritt-Schnellstart
├── CLAUDE.md                            # Persönliche Agent-Config (gitignored; lokal aus claude-sync.md)
├── AGENTS.md                            # Agent-Onboarding (gitignored)
├── Agents-gpt-gemini.md                 # KI-Onboarding für ChatGPT/Gemini
├── README.md                            # Diese Datei
└── .gitignore

```

---

> **Hinweis zur Struktur:** Der Backend-Code liegt unter **`04-Source-code/`** — das **P0-Grundgerüst steht** (FastAPI-Skelett, `GET /v1/health`, MariaDB-Setup **nativ** (Pi via Tunnel / lokal; kein Docker → E-35)). Struktur-/Setup-Detail siehe `04-Source-code/README.md` und `Backend-Konzept §7`. `.github/workflows/` (CI/CD) ist noch geplant.



## 🎯 Kernauftrag & Scope (G2)

**G2 baut:**
- Daten-**Ingest** (**Pull-Poller**: G2 ruft `GET /current` bei G1 ab, Intervall ≤ 60 s, selbst bestimmt)
- **Datenhaltung** (**MySQL/MariaDB** — durch Geschäftsleitung vorgegeben)
- **Vereisungsbewertung** (4-Stufen-Logik: 🟢🟡🟠🔴)
- **Alarm-Generierung** (Schweregrad, Hysterese)
- **Prognose** (30-min-Vorlauf)
- **API** (Serving für Frontend, Abfragen, Konfiguration)
- **Logging/Audit** (append-only, Compliance)

**G2 baut NICHT:**
- Sensor-Hardware/Messung → **Gruppe 1** (G2 definiert Format)
- Visualisierung/UI → **Gruppe 3** (G2 liefert Daten)

**Die Naht = API + Datenmodell** — das ist das kritische Interface.

> **🔄 Naht-Entscheidung (mit G1 abgestimmt, 22.06.2026 — E-31):** Die Datenübergabe G1 → G2 läuft als
> **Pull**, nicht als Push. **G1 stellt bereit:** `GET /current` (liefert **alle** aktuellen Messwerte als
> **einen** Snapshot mit **einem** gemeinsamen Mess-Zeitstempel `measured_at`, UTC/ISO-8601) und `GET /health`
> (Verfügbarkeit). **G2 baut** einen **Poller**, der `GET /current` in einem **selbst bestimmten Intervall
> (≤ 60 s)** abruft, validiert (Bereich, Stale, Defekt), persistiert und bewertet. Es gibt **keinen** von G2
> gehosteten `POST /readings`-Endpoint mehr. **Fail-safe (NF-01):** Erreichbarkeit (`/health`/Timeout)
> getrennt von Datenaktualität (`measured_at` zu alt → stale) prüfen — bei beidem **nie GRÜN**.

---

## 📊 Datenfluss (Backend)

```
  (G1 — Sensoren, stellt GET /current + GET /health bereit)
         ↑  Pull (G2 pollt, Intervall ≤ 60 s)
   G2-Poller ──→ GET /current  (1 Snapshot + measured_at, UTC)
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
   │  Input: T_s, ΔT (Taupunkt-Abstand), RH  │
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
   │  API-Serving (alle Endpoints /v1/):     │
   │   GET /v1/assessment/current            │
   │   GET /v1/alarms/stream (SSE → Push)    │
   │   GET /v1/alarms (Zustand/Resync)       │
   │   GET /v1/readings?from&to              │
   └─────────────────────────────────────────┘
         ↓ (G3 holt per GET; Alarme push via SSE)
    (an G3 — Frontend)
```

---

## 🔑 Entscheidungskategorien (Vereisungslogik)

Definiert in **`02-Arbeitsdokumente/Schwellenwerte.md §2`**:

| Stufe | Bedingung | Bedeutung |
|---|---|---|
| 🟢 **GRÜN** | `T_s > +1,0 °C` | Kein Vereisungsrisiko |
| 🟡 **GELB** | `T_s ≤ +1,0 °C` + trocken / OR Prognose `T_s ≤ 0 °C` in ≤ 30 min | Beobachtung + Vorwarnung |
| 🟠 **ORANGE** | `T_s ≤ 0,0 °C` + Feuchte vorhanden (`ΔT ≤ 1,0 °C`) | Vereisung wahrscheinlich → Warnung |
| 🔴 **ROT** | `T_s ≤ 0,0 °C` **und** `ΔT ≤ 0 °C` | **Aktive Eisbildung** → Alarm + Quittierung |

> **3-Faktor-Bewertung (E-32):** Die Logik nutzt **drei** Faktoren — Oberflächentemperatur `T_s`,
> Taupunkt-Abstand `ΔT` und Luftfeuchte `RH`. **Niederschlag ist als Faktor gestrichen** (Customer-Scope).
> Schwellen (0 °C / 1,0 °C) sind **Dummy-Startwerte**, parametrierbar (NF-05) — finale Werte von G1.
>
> **Feuchte = Oberflächennähe zum Taupunkt (E-33):** „Feuchte vorhanden" := `ΔT (T_s − T_d) ≤ 1,0 °C`,
> also an die **Oberfläche** gebunden (Nähe zum Taupunkt = reale Kondensations-/Reifgefahr). Der frühere
> Luft-`RH ≥ 90 %`-Trigger ist **komplett entfernt** — Luftfeuchte sagt nichts über die Oberfläche
> (Vorfall 1: 92 % **Luft**feuchte bei trockener Oberfläche → `ΔT > 1,0` → **GELB**, kein Fehlalarm).
> `RH`/`T_a` fließen nur **indirekt** über den Taupunkt `T_d` (Magnus) in `ΔT` ein; **keine** neue
> Messgröße. Das `humidity_pct` im `GET /current`-Snapshot ist **Luft**feuchte (nur `T_d`-Input).

**Beide dokumentierten Vorfälle gelöst:**
- Vorfall 1 (−2,1 °C Luft, 92 % **Luft**feuchte, trockene Oberfläche): `ΔT > 1,0` → **GELB** (kein Fehlalarm)
- Vorfall 2 (+1,2 °C Luft, Oberfläche < 0 °C): **ORANGE/ROT** (Vereisung erkannt)

---

## 📑 Wichtige Deliverables

### Funktionale & Nicht-Funktionale Anforderungen
**Datei:** `02-Arbeitsdokumente/Usecase-quick.md`  
**Inhalt:** FA-01–12 (z. B. Oberflächentemperatur-/Taupunkt-/Feuchtemessung, Alarmierung, Logging)  
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
- Tech-Stack (FastAPI + Pydantic, **MySQL/MariaDB** [GL-Vorgabe], rohes PyMySQL [kein ORM, E-35], HTTP-Pull-Poller `GET /current`)
- Ausbaustufen T0–T3
- Schnittstellen zu G1 (Sensorik) & G3 (Frontend)

### Projektplan & Kanban
**Datei:** `02-Arbeitsdokumente/Tasks+Projektplan.md`  
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
- Cadence (Standup 2–3×/Woche, Team-Sync 1×/Woche)

---

## 🛠️ Tech-Stack (T0)

| Komponente | Empfehlung | Alternativen |
|---|---|---|
| **Sprache** | Python 3.11+ | — |
| **Framework** | FastAPI | Flask, Node/Express |
| **Validierung** | Pydantic v2 | — |
| **Datenbank** | **MySQL 8 / MariaDB** — durch GL vorgegeben (dev = prod, native MariaDB; kein Docker → E-35) | ~~SQLite, PostgreSQL~~ (verworfen, s. Backend-Konzept §6a) |
| **DB-Zugriff** | rohes PyMySQL + Repository-Pattern · handgeschriebenes `schema.sql` (kein ORM/Alembic → E-35) | ~~SQLAlchemy~~ |
| **Übertragung** | HTTP REST **Pull** — G2-Poller ruft G1s `GET /current` ab (≤ 60 s) | MQTT (später) |
| **Testing** | pytest + coverage | unittest |
| **Logging** | Python `logging` + structlog | — |

> **DB ist vorgegeben** (`02-Arbeitsdokumente/Surprise Anforderungen.txt`); Analyse + Risiken in
> `Backend-Konzept.md §6a`. Übrige Bausteine **begründen** im Entscheidungslogbuch (Team-Kompetenz, Prototyp-Fokus).

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
4. 02-Arbeitsdokumente/Tasks+Projektplan.md    # Wer macht was bis wann?
5. 02-Arbeitsdokumente/Team-Organisation+Regeln.md # Wie arbeiten wir zusammen?
```

### 3. Umgebung aufsetzen
```bash
cd 04-Source-code
py -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
# MariaDB: native — Pi via SSH-Tunnel ODER lokale Installation (kein Docker → E-35); Zugang via .env
```
> Setup-/Agenten-Tooling lebt in `Devteam-vibecodes` (siehe **⚙️ Setup & Tooling** oben).

### 4. Server starten
```bash
# T0-Ziel: GET /v1/health → 200 OK
uvicorn src.main:app --reload                # → http://127.0.0.1:8000
```

### 5. Tests schreiben & laufen
```bash
pytest                  # alle Tests
pytest --cov=src        # mit Coverage (Bewertungslogik = Priorität 1, ≥ 80 %)
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
1. **Titel:** `[Phase/Epic] Kurzbeschreibung`
2. **Description:** Was, warum, wie; Links zu Docs
3. **Review:** Architekt (Lucas V.) bestätigt Contract
4. **Tests:** mindestens grün vor Merge
5. **Merge:** Squash oder Rebase (kein Clutter)

---

## 📐 Interne Conventions

### Code-Struktur (`04-Source-code/src/`)
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

#### zu G1 (Sensorik) — **Pull**: G1 ist Server, G2 ist Client
- **`GET /current`-Snapshot** — welche Felder, welche Einheiten, gemeinsamer `measured_at` (UTC)?
- **`GET /health`** — Verfügbarkeits-Check (200 ok / 503 fault)
- **Poll-Intervall** — G2 bestimmt selbst (≤ 60 s); keine Push-Frequenz seitens G1 nötig
- **Team-Sync:** 1×/Woche (Anfang Woche 2)

#### zu G3 (Frontend)
- **`GET /v1/assessment/current`-Response** — welche Felder, Formatierung?
- **`GET /v1/alarms`** — wie werden Alarme visualisiert?
- **Team-Sync:** 1×/Woche (Anfang Woche 2)

---

## 📚 Dokumentation & Entscheidungslogbuch

**Jede Entscheidung** (Tech-Stack, Schwellenwert-Anpassung, Architektur-Pivot) muss dokumentiert werden:

### Was dokumentieren?
- **Was:** Entscheidung selbst
- **Warum:** Kontext + Alternativen
- **Folgen:** Impact auf andere Tasks
- **Wer + Wann:** Owner + Datum

### Wo dokumentieren?
- **Technisch:** `02-Arbeitsdokumente/Entscheidungslog-Lucas-Systemarchitektur.md` (existiert, lebendes Dokument) + PR-Beschreibungen
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
- **Team-Syncs** regelmäßig halten

---

## 📞 Kontakt & Rollen

| Rolle | Person | Verantwortung |
|---|---|---|
| Teilprojektleiter | Landmann, Lucas | Scope, Blocker, Außenkontakt |
| **Systemarchitekt** | **Vöhringer, Lucas** + Petzold, Johannes | API, Datenmodell, Schnittstellen |
| **Backend-Lead** | **Vöhringer, Lucas** | Code-Quality, Reviews, Backend-Koordination |
| Backend-Devs | Hartling, Leon · Ganter, Luca · Moritz, Andreas · Sarkhab, Arash | Ingest, Persistenz, Bewertungslogik, API |
| Test / Review | Mohammadi, Azezoo · Berger, Amelie | Definition of Done, Testprotokoll |
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

*Letzte Aktualisierung: 25.06.2026 — G2 Backend & Entscheidungslogik (API-Contract v1.0 eingefroren; `/v1`-Endpoints; E-35 PyMySQL/native MariaDB)*
