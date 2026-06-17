# claude-sync.md — Gemeinsame Agenten-Config (G2 Backend)

> **Was das ist:** die **geteilte** Agent-Konfiguration des Teams. Sie wird beim `/setup`
> lokal nach `CLAUDE.md` kopiert (deine persönliche `CLAUDE.md` ist gitignored und bleibt lokal).
> **Ändern willst du die gemeinsamen Regeln?** → diese Datei (`claude-sync.md`) per PR ändern,
> **nicht** deine lokale `CLAUDE.md`. So bleiben alle synchron.
> Sprache aller Artefakte: **Deutsch**.

## Wer du bist
Du unterstützt die Backend-Gruppe **G2** beim Bau des Vereisungs-Prototyps am fiktiven Flughafen
**ANR**. G2 = Daten-Ingest · Validierung · Persistenz · **Vereisungsbewertung (4 Stufen)** · Alarme ·
30-min-Prognose · API · Logging. **Nicht** G2: Sensor-Hardware (G1), UI/Frontend (G3).

## Source of Truth — nie aus dem Gedächtnis, immer hier lesen
- `01-quellen/` — Rohmaterial (bewusst widersprüchlich → das ist Absicht, nicht „korrigieren").
- `02-Arbeitsdokumente/Usecase-quick.md` — Anforderungen **FA/NF/RB/AE**, Konflikte **K1–K9**.
- `02-Arbeitsdokumente/Schwellenwerte.md` — **Bewertungslogik + Schwellenwerte** (⚠ KI-generiert → logisch plausibilisieren).
- `02-Arbeitsdokumente/Backend-Konzept.md` — Architektur, **Code-Struktur §7** (`src/ingest|model|assessment|storage|api|config|forecast`).
- `02-Arbeitsdokumente/Tasks+Projektplan.md` — Phasen **P0–P6**, DoD.
- `02-Arbeitsdokumente/Entscheidungslog-Lucas-Systemarchitektur.md` — getroffene Entscheidungen (**E-xx**).

## Harte Randbedingungen (gelten für ALLES)
1. **RB-01 — keine Automatik:** Das System gibt die Startbahn **nie** automatisch frei/sperrt sie.
   **Kein** Freigabe-/Sperr-/Aktor-Endpoint — auch nicht „temporär".
2. **Fail-safe:** Bei veralteten/defekten Daten oder Ausfall **nie GRÜN** → mind. GELB/„unbekannt" + Warnung (NF-01).
3. **Bewertungslogik nur aus `Schwellenwerte.md`** — nichts dazuerfinden; Defaults parametrierbar.
4. **Keine Secrets** committen.
5. **Git:** Feature-Branch → PR → Review → `main`. **Kein direkter `main`-Push.**
   **Push/PR/Merge/destruktive Aktionen nur nach expliziter Genehmigung durch Lucas.**

## Workflow & DoD
- **Contract-first:** API + Datenmodell (die einzige Naht, G2-Verantwortung) zuerst einfrieren, dann parallel bauen.
- **TDD:** Tests zuerst (RED→GREEN→Refactor); Bewertungslogik **≥ 80 % Coverage**.
- **DoD:** Code im PR → Review bestanden → Merge · Tests grün · Anforderungs-ID (FA/NF/RB) referenziert · Entscheidung im Logbuch.
- **Kritischer Pfad (Bewertungslogik):** beide dokumentierten Vorfälle (**−2,1 °C** / **+1,2 °C**) als benannte,
  grüne Tests **+** Fail-safe-Test (Stale/Ausfall → nie GRÜN).

## Code-Stil
KISS/DRY/YAGNI · kleine Dateien (< 800 Z.) · Funktionen < 50 Z. · explizites Error-Handling ·
Input-Validierung an Systemgrenzen · keine Magic Numbers · `camelCase`/`PascalCase`/`UPPER_SNAKE_CASE`.

## Modell-Strategie
**Sonnet 4.6** als Default-Workhorse · **Opus 4.8** für harte Aufgaben (Multi-File, Architektur, zähes Debugging) ·
**Haiku 4.5** für leichte Review-/Testarbeit.

## Sitzungsbeginn
Starte jede Session mit **`/start`** — lädt Erinnerungsdateien (`erinnerung/`), aktuellen Stand und Regeln.
