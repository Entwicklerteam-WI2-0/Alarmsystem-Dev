# 05 — Fortschrittslog (G2 Backend · Vereisungserkennung ANR)

> **Zweck:** Schnelle Orientierung über den **aktuellen Code-Stand** des Backends — welche Module/Funktionen
> stehen und welche **Commits / Pull Requests** sie gebracht haben. Ergänzt das `erinnerung/`-Journal
> (Session-/Prozess-Sicht) um die **Code-Sicht**. Keine Use-Case-Werte hier — die liegen in den
> `02-Arbeitsdokumente/`. **Pflege:** bei jedem nennenswerten Merge in `main` einen Eintrag in §2 ergänzen
> und §1 aktualisieren. Sprache: Deutsch.

## 1. Aktueller Stand — Snapshot (Stand: 2026-06-22)

**Branch-Lage:** `main` ist der konsolidierte Stand. P0-Grundgerüst + MySQL-Setup sind gemergt.

### Steht / vorhanden
- **P0-Grundgerüst** (PR #27): FastAPI-Skelett, `GET /health`, Modulstruktur
  `04-Source-code/src/{ingest,model,assessment,storage,api,config,forecast}/`, `tests/test_health.py`.
- **MySQL/MariaDB-Setup** (PR #26, #21): `04-Source-code/docker-compose.yml` (MariaDB 11), `.env.example`,
  Dependencies `sqlalchemy 2.0`, `pymysql 1.1`, `alembic 1.13`.
- **`migrations/`**-Ordner angelegt (Alembic, noch leer).
- **Doku** MySQL-aktualisiert: Backend-Konzept §6/§6a, README-Tech-Stack, Entscheidungslog **E-29**
  (DB-Strategie MySQL/MariaDB, GL-Vorgabe).

### Offen — kritischer Pfad (nächste Schritte)
- **Contract/Naht (E-02):** Datenmodell-Schema + OpenAPI v1 einfrieren. *(Owner: Lucas — festgelegt)*
- **Persistenz:** SQLAlchemy-Modelle (DTB-12) → erste Alembic-Migration (DTB-54) → Engine-Bootstrap
  (DTB-55) → Repository (DTB-28).
- **Bewertungslogik (DTB-38):** 4-Stufen, DB-frei, Kern-IP; beide Vorfall-Tests + Fail-safe, ≥ 80 % Coverage.
- **docker-compose (DTB-53):** Healthcheck + utf8mb4 ergänzen (Grundgerüst steht bereits).

### Bekannte offene Punkte (Doku / Orga)
- Root-`README.md` Struktur-/Setup-Sektion noch auf `src/`-Root + „noch nicht im Repo" (statt
  `04-Source-code/`, `pip`/`uvicorn`) — Korrektur ausstehend.
- E-ID-Kollision im Entscheidungslog (E-29 mehrfach belegt) — Auflösung **E-30/E-31/E-32** ausstehend
  (DRI Lucas).
- `Projektplan-Jira-Backlog-G2.md` noch SQLite-Stand; das Jira-Board ist bereits MySQL-überarbeitet.

## 2. Änderungs-Log (Commits / Pull Requests)

| Datum | PR / Commit | Inhalt |
|---|---|---|
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
