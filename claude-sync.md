# claude-sync.md — Gemeinsame Agenten-Config (G2 Backend)

> **Was das ist:** die **geteilte** Agent-Konfiguration des Teams. Sie wird beim `/setup`
> lokal nach `CLAUDE.md` kopiert (deine persönliche `CLAUDE.md` ist gitignored und bleibt lokal).
> **Ändern willst du die gemeinsamen Regeln?** → diese Datei (`claude-sync.md`) per PR ändern,
> **nicht** deine lokale `CLAUDE.md`. So bleiben alle synchron.
> Sprache aller Artefakte: **Deutsch**. · **Stand: 2026-06-23** (Stack-Pivot E-35).

## Wer du bist
Du unterstützt die Backend-Gruppe **G2** beim Bau des Vereisungs-Prototyps am fiktiven Flughafen
**ANR**. G2 = Daten-Ingest · Validierung · Persistenz · **Vereisungsbewertung (4 Stufen)** · Alarme ·
30-min-Prognose · API · Logging. **Nicht** G2: Sensor-Hardware (G1), UI/Frontend (G3).

> **40 % Einzelleistung = NUR Prüfungs-Notengewicht, KEINE Arbeits-/Architekturregel.** Triff und
> empfiehl technische Entscheidungen wie ein kompetenter Engineering-Partner; delegiere sie nicht
> mit Verweis auf die 40 % an den Menschen zurück und lass Arbeitsdokumente nie absichtlich leer.

## Source of Truth — nie aus dem Gedächtnis, immer hier lesen
- `01-quellen/` — Rohmaterial (bewusst widersprüchlich → das ist Absicht, nicht „korrigieren").
- `02-Arbeitsdokumente/Usecase-quick.md` — Anforderungen **FA/NF/RB/AE**, Konflikte **K1–K9**.
- `02-Arbeitsdokumente/Schwellenwerte.md` — **Bewertungslogik + Schwellenwerte** als priorisierte Kaskade
  (⚠ KI-generiert / Dummy → logisch plausibilisieren; G1-Finalwerte stehen aus → `config/` parametrierbar halten).
- `02-Arbeitsdokumente/Backend-Konzept.md` — Architektur, **Code-Struktur §7**.
- `02-Arbeitsdokumente/Stack-Entscheidung-P0.1.md` — **aktueller Stack (E-35)**: FastAPI · MariaDB · PyMySQL · nativ.
- `02-Arbeitsdokumente/Umstellung-Pull-3Faktor-Faktenblatt.md` — **G1-Naht Pull + 3-Faktor-Bewertung** (E-31/E-32).
- `02-Arbeitsdokumente/Tasks+Projektplan.md` + `02-Arbeitsdokumente/Projektplan-Jira-Backlog-G2.md` — Phasen **P0–P6**,
  DoD, **Jira-Backlog (Projekt DTB)**.
- `02-Arbeitsdokumente/Entscheidungslog-Lucas-Systemarchitektur.md` — getroffene Entscheidungen (**E-xx**).
- `05-Fortschrittslog/Fortschrittslog.md` — chronologischer Fortschritt.

## Stack (Stand E-35 — DB-Mandat MySQL/MariaDB bleibt)
- **FastAPI** (HTTP) · **MariaDB/MySQL** verbindlich (E-29, Geschäftsleitungs-Vorgabe, **ersetzt SQLite**).
- **Rohes PyMySQL hinter Repository-Pattern** — **kein** SQLAlchemy; **parametrisierte Queries Pflicht** (SQL-Injection).
- **Handgeschriebenes `schema.sql`** (`migrations/`) — **kein** Alembic.
- **Native MariaDB** (Pi via Tunnel / lokal) — **kein** Docker.
- **Backend-Code-Root: `04-Source-code/`** (`src/ingest|model|assessment|storage|api|config|forecast` + `tests/`).

## Harte Randbedingungen (gelten für ALLES)
1. **RB-01 — keine Automatik:** Das System gibt die Startbahn **nie** automatisch frei/sperrt sie.
   **Kein** Freigabe-/Sperr-/Aktor-Endpoint — auch nicht „temporär".
2. **Fail-safe:** Bei veralteten/defekten Daten oder Ausfall **nie GRÜN** → mind. GELB/„unbekannt" + Warnung (NF-01).
3. **Bewertungslogik nur aus `Schwellenwerte.md`** — nichts dazuerfinden; Defaults parametrierbar (`config/`).
   **3 Faktoren:** Oberflächentemp `T_s` + Taupunkt-Abstand `ΔT` + Feuchte `RH` (Niederschlag gestrichen, E-32).
   „Feuchte vorhanden" := `ΔT ≤ 1,0` an der Oberfläche, **nicht** Luft-`RH` (E-33). Kaskade: erste zutreffende Stufe gewinnt, ROT-Vorrang (E-34).
4. **Keine Secrets** committen (`.env` lokal; DB-Zugang via Env).
5. **Git:** Feature-Branch → PR → Review → `main`. **Kein direkter `main`-Push.**
   **Push/PR/Merge/destruktive Aktionen nur nach expliziter Genehmigung durch Lucas.**

## Workflow & DoD
- **Contract-first:** API + Datenmodell (die einzige Naht, G2-Verantwortung) zuerst einfrieren, dann parallel bauen.
- **G1-Naht = Pull (E-31):** G2 **pollt** G1 `GET /current` (Snapshot + `measured_at`, Intervall ≤ 60 s) + `GET /health`.
  **Kein** G2-`POST /readings`. G2 serviert an G3 `GET /assessment/current`.
- **TDD:** Tests zuerst (RED→GREEN→Refactor); Bewertungslogik **≥ 80 % Coverage**.
- **DoD:** Code im PR → Review bestanden → Merge · Tests grün · Anforderungs-ID (FA/NF/RB) referenziert · Entscheidung im Logbuch.
- **Kritischer Pfad (Bewertungslogik):** beide dokumentierten Vorfälle (**−2,1 °C** / **+1,2 °C**) als benannte,
  grüne Tests **+** Fail-safe-Test (Stale/Ausfall → nie GRÜN).

## Code-Stil
KISS/DRY/YAGNI · kleine Dateien (< 800 Z.) · Funktionen < 50 Z. · explizites Error-Handling ·
Input-Validierung an Systemgrenzen · keine Magic Numbers · **Python-Naming:** `snake_case` (Funktionen/Variablen) ·
`PascalCase` (Klassen/Pydantic-Modelle) · `UPPER_SNAKE_CASE` (Konstanten).

## Modell-Strategie
**Sonnet 4.6** als Default-Workhorse · **Opus 4.8** für harte Aufgaben (Multi-File, Architektur, zähes Debugging) ·
**Haiku 4.5** für leichte Review-/Testarbeit (auf einzelnen Maschinen ggf. auf Sonnet umgeleitet).

## Sitzungsbeginn
Starte jede Session mit **`/start`** — lädt Erinnerungsdateien (`erinnerung/`), aktuellen Stand und Regeln.
