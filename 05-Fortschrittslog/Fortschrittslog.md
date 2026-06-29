# 05 — Fortschrittslog (G2 Backend · Vereisungserkennung ANR)

> **Zweck:** Schnelle Orientierung über den **aktuellen Code-Stand** des Backends — welche Module/Funktionen
> stehen und welche **Commits / Pull Requests** sie gebracht haben. Ergänzt das `erinnerung/`-Journal
> (Session-/Prozess-Sicht) um die **Code-Sicht**. Keine Use-Case-Werte hier — die liegen in den
> `02-Arbeitsdokumente/`. **Pflege:** bei jedem nennenswerten Merge in `main` einen Eintrag in §2 ergänzen
> und §1 aktualisieren. Sprache: Deutsch.

## 1. Aktueller Stand — Snapshot (Stand: 2026-06-23)

**Branch-Lage:** `main` = konsolidierter Stand (Stack-Blatt + E-35 gemergt). DTB-12-Datenmodell offen als **PR #37**.

### Steht / vorhanden
- **P0-Grundgerüst** (PR #27): FastAPI-Skelett, `GET /health`, Modulstruktur
  `04-Source-code/src/{ingest,model,assessment,storage,api,config,forecast}/`, `tests/test_health.py`.
- **Stack final (P0.1, E-35):** Python/FastAPI/Pydantic/Uvicorn + **rohes PyMySQL** (kein ORM) +
  **MySQL/MariaDB** + HTTP-Pull. SQLAlchemy/Alembic **entfernt**; Deps: `fastapi`, `uvicorn[standard]`,
  `pymysql`. Doku: `Stack-Entscheidung-P0.1.md`, Entscheidungslog **E-35** (revidiert E-29-Umsetzung;
  DB-Mandat MySQL bleibt).
- **Datenmodell (DTB-12, PR #37, in Review):** 6 Pydantic-Modelle (`src/model/schemas.py`) + Enums
  (`enums.py`, inkl. `unknown`/Fail-safe), **`migrations/schema.sql`** (MariaDB-DDL: utf8mb4, DATETIME(3) UTC,
  CHECK-Enums, FKs), `tests/test_model.py` (**8 grün**).
- **MySQL/MariaDB-Setup** (PR #26, #21, E-29): native MariaDB 11 (Pi), `.env.example`. **Kein Docker** mehr
  (E-35) → `docker-compose.yml` noch zu entfernen.

### Offen — kritischer Pfad (nächste Schritte)
- **Naht-Freeze (E-02):** OpenAPI v1 (DTB-19) + `reading`-Felder mit G1 bestätigen (**P1.4**). *(Owner: Lucas)*
- **Persistenz (DTB-28):** Repository auf **rohem PyMySQL** (parametrisierte Queries) → Connection-Helper
  (DTB-55) → `schema.sql` einspielen (DTB-54). *(kein ORM/Alembic, E-35)*
- **Bewertungslogik (DTB-38):** 4-Stufen, DB-frei, Kern-IP; beide Vorfall-Tests + Fail-safe, ≥ 80 % Coverage.
- **CI (DTB-11):** DB-Bereitstellung klären (MySQL-Service-Container vs. nur DB-freie Tests).

### Bekannte offene Punkte (Doku / Orga)
- Prosa-Spiegel **Backend-Konzept §6/§7** + **README** noch auf SQLAlchemy/Docker — E-35-Angleich läuft (parallel).
- `Projektplan-Jira-Backlog-G2.md` noch SQLite-Stand.
- `docker-compose.yml` entfernen (E-35).

## 2. Änderungs-Log (Commits / Pull Requests)

| Datum | PR / Commit | Inhalt |
|---|---|---|
| 2026-06-29 | (lokal, uncommitted) | **DTB-27 Anzeige-Hysterese verdrahtet** — `RiskHysterese` in den Live-Pfad integriert; `displayed_risk_level`-Feld (Schema + DB + Repo + Service); `uebernimm_unknown()`-Tick für Fail-safe-Pfade (State-Desync nach Stale behoben); Serve-Pfad liefert entprellte Stufe an G3; `derive_explanation` erklärt angezeigte Stufe (Blocker 2); Alarm-Gen bleibt auf rohem `risk_level`. 2 neue Testdateien (Recovery-nach-Stale, Serve entprellt, Persistenz). **824 Tests grün, 100 % Coverage auf `assessment/` + `alarm/riskhysterese`.** |
| 2026-06-23 | #37 (`d24ee92`) | DTB-12 Datenmodell — 6 Pydantic-Modelle + Enums + `schema.sql`, kein ORM (E-35); 8 Tests grün *(in Review)* |
| 2026-06-23 | `5000baa` | E-35: Wechsel auf rohes PyMySQL, SQLAlchemy/Alembic entfernt |
| 2026-06-23 | `5c09857` | Stack-Entscheidung P0.1 (Stack-Blatt) |
| 2026-06-22 | #27 (`29528b4`) | P0-Grundgerüst — FastAPI-Skelett, `/health`, MySQL-Setup |
| 2026-06-22 | #26 (`f44649c`) | Pi- + MariaDB-Setup |
| 2026-06-22 | #21 (`bd4950c`) | MySQL-Vorgabe der GL in Backend-Konzept, README & Entscheidungslog (E-29) |
| 2026-06-22 | #25 (`6902974`) | erinnerung: append-only Pflege-Regel |
| 2026-06-22 | #23 / #24 | Session-Doku / erinnerung-Update |

## 3. Vorlage für neue Einträge

Neue Zeile in §2 (oben in die Tabelle, neueste zuerst):

    | <YYYY-MM-DD> | #<PR> (`<hash>`) | <Kurzbeschreibung der Code-Änderung> |

Bei größeren Merges zusätzlich §1 aktualisieren: was ist jetzt fertig (→ „Steht / vorhanden"),
was rückt nach (→ „Offen — kritischer Pfad").
