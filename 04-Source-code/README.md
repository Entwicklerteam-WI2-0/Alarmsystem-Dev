# G2-Backend — Vereisungserkennung ANR

Backend-Repo der Gruppe 2 (FastAPI · MySQL/MariaDB · SQLAlchemy). Struktur nach
`../02-Arbeitsdokumente/Backend-Konzept.md` §7, Tasks nach `../02-Arbeitsdokumente/Tasks+Projektplan.md`.

## Struktur
- `src/ingest/` — REST-Ingest (`POST /readings`), Eingangsvalidierung
- `src/model/` — Datenklassen / Schemas
- `src/assessment/` — Vereisungslogik (4-Stufen) — Kernmodul, hohe Testabdeckung
- `src/storage/` — DB-Zugriff (Repository-Pattern, SQLAlchemy -> MySQL/MariaDB)
- `src/api/` — Serving-Endpoints für G3
- `src/config/` — Schwellen/Parameter (parametrierbar)
- `src/forecast/` — 30-min-Prognose (T3)
- `migrations/` — Alembic-Schema-Migrationen
- `tests/` — Unit-/Integrationstests
- `config/` — Default-Schwellenwerte (Dummy, parametrierbar)

## Setup (lokal, Windows)
    cd 04-Source-code
    py -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements-dev.txt
    docker compose up -d db          # MariaDB (dev = prod)
    uvicorn src.main:app --reload    # -> http://127.0.0.1:8000

## Tests
    pytest                 # alle Tests
    pytest --cov=src       # mit Coverage (Ziel: Bewertungslogik >= 80 %)

## Health-Check
`GET /health` -> `{"status": "ok"}` (P0.3)
