# Stack-Entscheidung (P0.1 / DTB-2)

> **Zweck:** Konsolidiertes, zitierbares Deliverable der **finalen Technologie-Stack-Wahl** des Backends (G2).
> Bündelt die über mehrere ADR-Einträge verteilte Entscheidung an **einer** Stelle und räumt die veralteten
> Vor-Stände (SQLite, HTTP-POST, SQLAlchemy/Alembic, Docker) auf. **Bewertungsrelevant** (Nachvollziehbarkeit).
> **Autor:** Lucas Vöhringer (Systemarchitekt) · **Stand:** 2026-06-23 · **Task:** DTB-2 / P0.1.
> **Detail-Begründungen (ADR):** `Entscheidungslog-Lucas-Systemarchitektur.md` E-08/E-29/E-30/E-31/**E-35**;
> Architektur-Spec: `Backend-Konzept.md §6/§6a`. **Bei Konflikt gewinnen die E-xx-Einträge + dieses Blatt.**

---

## 1. Finaler Stack (gesetzt)

| Schicht | Wahl | Version (Repo) | Bezug |
|---|---|---|---|
| Sprache | **Python** | `>= 3.12` (`pyproject.toml`) | E-08 |
| Web-/API-Framework | **FastAPI** | `>= 0.115` | E-08 |
| Validierung/Schemas | **Pydantic** (mit FastAPI) | (FastAPI-Dep) | E-08 |
| ASGI-Server | **Uvicorn** `[standard]` | `>= 0.30` | E-08 |
| Persistenz / DB-Treiber | **rohes PyMySQL** (direkt, **kein ORM**) hinter Repository-Pattern; **parametrisierte Queries Pflicht** | `>= 1.1` | E-04, **E-35** |
| Datenbank | **MySQL / MariaDB** (durchgängig) | MariaDB 11.8 (Pi) | **E-29 (GL-Vorgabe)** |
| Schema / Migrationen | **handgeschriebenes `schema.sql`** (DDL; **kein Alembic**) | — | **E-35** |
| DB-Bereitstellung (dev) | **native MariaDB** (geteilte Pi via Tunnel / lokal nativ; **kein Docker**) | MariaDB 11.8 (Pi) | **E-35** |
| Test / Lint | **pytest** · **ruff** | `pyproject.toml` | E-07, P0.3 |
| Daten-Protokoll (G1→G2) | **HTTP, Pull** — G2 pollt G1 `GET /current` + `GET /health` | — | **E-31 (löst E-30/Push ab)** |
| API-Protokoll (G2→G3) | **HTTP REST** (G3 pollt G2 per `GET`) | — | E-04, E-31 |

> **Hinweis Schwellenwerte:** unberührt vom Stack. Bewertungslogik bleibt eine reine, DB-freie Funktion;
> Schwellen parametrierbar über `config/` (NF-05, E-14) — nie hardcoden (G1-Finalwerte ausstehend).

## 2. Begründung (kompakt — Details in den E-xx)

- **Python + FastAPI + Pydantic + Uvicorn (E-08):** minimaler, schnell produktiver REST-Stack mit
  eingebauter Schema-Validierung — passend für einen 3-Wochen-Prototyp eines Anfänger-Teams.
- **MySQL/MariaDB durchgängig (E-29):** per Geschäftsleitung verbindlich vorgegeben
  (`Surprise Anforderungen.txt`); kein schwerwiegender technischer Gegengrund (`Backend-Konzept §6a`).
- **Persistenz: rohes PyMySQL statt ORM (E-35):** Für ~6 simple Tabellen ist ein ORM + Migrationsframework
  Overkill; rohes, **parametrisiertes** SQL hinter dem Repository-Pattern ist für ein ~2.-Sem.-Team
  verständlicher und hat weniger bewegliche Teile. Der kritische Pfad (Bewertungslogik) bleibt DB-frei.
  Schema als handgeschriebenes `schema.sql`; Alembic entfällt.
- **Kein Docker (E-35):** Die Docker-Parität (E-29-Ziel „dev = prod") ist **ohne Docker erreichbar**, weil
  bereits eine **echte native MariaDB auf dem Pi** läuft. Dev verbindet gegen die Pi-MariaDB (Tunnel) oder
  eine lokale native MariaDB; `docker-compose.yml` entfällt. Es bleibt durchgängig MySQL/MariaDB.
- **HTTP-Pull statt Push (E-31, löst E-30 ab):** G1 stellt `GET /current` (+ `/health`) bereit, G2 pollt
  (Intervall ≤ 60 s). Einheitliches Request/Response-Modell; Fail-safe (NF-01) durch getrennte Prüfung von
  Erreichbarkeit (`/health`/Timeout) und Datenaktualität (`measured_at` stale).

## 3. Verworfene Alternativen (Verweis)

| Verworfen | Warum | Bezug |
|---|---|---|
| **SQLAlchemy ORM** | Overkill + Lernkurve für 3-Wochen-Anfängerprojekt | E-35 |
| **SQLAlchemy Core** | Kompromiss (Injection-Schutz ohne ORM-Last); verworfen zugunsten max. Einfachheit — Schutz stattdessen per parametrisierte Queries + Review | E-35 |
| **Alembic** | Migrationsframework unnötig bei stabilem `schema.sql` für 6 Tabellen | E-35 |
| **Docker-Compose-MariaDB** | Einstiegshürde (Windows/WSL2) ohne Mehrwert — native Pi-MariaDB existiert | E-35 |
| **SQLite** (durchgängig oder dev-only) | widerspricht GL-Vorgabe; Dialekt-Drift-Risiko | E-29 |
| **PostgreSQL / TimescaleDB** | im Haus nicht etabliert (GL-Kriterium „bestehende Kompetenz") | E-29 |
| **Push (`POST /readings`, G2 hostet Ingest)** | durch G1-Realität überholt — G1 hostet einen Abfrage-Endpoint | E-30→E-31 |
| **Pull mit Einzel-Endpoints je Messgröße** | kein gemeinsamer Mess-Zeitpunkt → inkonsistente Snapshots | E-31 |

## 4. Aufgeräumte Vor-Stände (Drift behoben)

Dieses Blatt ist der **kanonische** P0.1-Stand. Überholt sind:
- **E-08** „SQLite + HTTP" → DB-Teil via **E-29** (MySQL), Protokoll via **E-31** (Pull).
- **EP-03** (21.06.) „FastAPI + SQLite + HTTP-POST" → doppelt überholt (E-29 + E-31).
- **E-29-Umsetzung** „SQLAlchemy + Alembic + Docker-Compose" → revidiert durch **E-35** (rohes PyMySQL +
  `schema.sql` + native MariaDB). Das **DB-Mandat MySQL/MariaDB** aus E-29 bleibt.
- **Offen / nachzuziehen:** `Backend-Konzept §6/§6a/§7`, beide `README.md` und
  `Projektplan-Jira-Backlog-G2.md` noch auf SQLAlchemy/Alembic/Docker (bzw. teils SQLite) — gegen E-35
  angleichen; `docker-compose.yml` entfernen.

## 5. DoD-Abgleich DTB-2 (P0.1)

- [x] Stack final: Python + FastAPI + Pydantic + **rohes PyMySQL + MySQL/MariaDB** + **HTTP-Pull** — §1.
- [x] GL-MySQL-Vorgabe angenommen + Verweis auf `Backend-Konzept §6a` — §2/§4.
- [x] Begründung + verworfene Alternativen dokumentiert — §2/§3 (+ ADR E-08/E-29/E-31/E-35).
- [x] Drift „SQLite+POST" (E-08/EP-03) aufgelöst — §4.
- [ ] Spiegel `Backend-Konzept` / READMEs / `Projektplan-Jira-Backlog-G2.md` + `docker-compose.yml` — offen, §4.
