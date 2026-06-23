# G2-Backend — Vereisungserkennung ANR

Backend-Repo der Gruppe 2 (FastAPI · MySQL/MariaDB · rohes PyMySQL, kein ORM). Struktur nach
`../02-Arbeitsdokumente/Backend-Konzept.md` §7, Tasks nach `../02-Arbeitsdokumente/Tasks+Projektplan.md`.

## Struktur
- `src/ingest/` — Poller gegen G1 (`GET /current`, `GET /health`), Eingangsvalidierung
- `src/model/` — Pydantic-Schemas + Enums (6 Entitäten: reading/assessment/alarm/acknowledgement/threshold_set/audit_log); DB-DDL in `migrations/schema.sql`
- `src/assessment/` — Vereisungslogik (4-Stufen) — Kernmodul, hohe Testabdeckung
- `src/storage/` — DB-Zugriff (Repository-Pattern, rohes PyMySQL → MySQL/MariaDB; kein ORM, E-35)
- `src/api/` — Serving-Endpoints für G3
- `src/config/` — Schwellen/Parameter (parametrierbar)
- `src/forecast/` — 30-min-Prognose (T3)
- `migrations/` — `schema.sql` (handgeschriebenes DDL; kein Alembic, E-35)
- `tests/` — Unit-/Integrationstests
- `config/` — Default-Schwellenwerte (Dummy, parametrierbar)

## Setup (lokal, Windows)
    cd 04-Source-code
    py -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements-dev.txt
    # MariaDB: native — Pi via SSH-Tunnel ODER lokale Installation (kein Docker, E-35)
    # Zugangsdaten über .env (s. .env.example), nie committen
    uvicorn src.main:app --reload    # -> http://127.0.0.1:8000

## Tests
    pytest                 # alle Tests
    pytest --cov=src       # mit Coverage (Ziel: Bewertungslogik >= 80 %)

## Health-Check (G2)
`GET /health` -> `{"status": "ok"}` (P0.3)

## Datenfluss
`G1 (Sensorik)` ──poll `GET /current`──▶ `Ingest/Validierung` ──▶ DB `reading` ──▶ `Bewertung` (4-Stufen)
──▶ `assessment` (+ ggf. `alarm`) ──▶ DB ──▶ `API` ──poll──▶ `G3 (Frontend)`.
**Fail-safe (NF-01):** bei Stale/Ausfall nie GRÜN → `unknown` + Warnung.

## Schnittstelle G1 → G2 (Contract, eingehend)

G1 liefert eine eigene Sensor-API; G2 pollt sie. Verbindlich:

```
GET /current → {
  "measured_at": "2026-06-22T14:03:05Z",   // PFLICHT — ein Zeitstempel für alle Werte
  "sensor_id": "anr-rwy-01",
  "surface_temp_c": -0.4,   // Pflicht-Trias für die Bewertung
  "air_temp_c": 1.2,        //
  "humidity_pct": 96,       //
  "pressure_hpa": 1013,     // optional/Kontext
  "status": "ok"
}

GET /health → 200 (ok) / 503 (fault)
```

`measured_at` und `/health` sind nicht verhandelbar; Feldnamen/Einheiten sonst Seam-Sync.

## Schnittstelle G2 → G3 (Serving, ausgehend)

G3 pollt G2 per `GET` (REST). Geplante Endpoints (Spec: DTB-19 / OpenAPI v1):
- `GET /assessment/current` — aktuelle Risikostufe (`green|yellow|orange|red|unknown`) + Faktoren + Zeitstempel
- `GET /alarms` · `POST /alarms/{id}/ack` (Quittierung — reine UI-/Audit-Aktion, **kein** Bahn-Aktor, RB-01)
- `GET /readings` — Historie

**Kein** Freigabe-/Sperr-Endpoint (RB-01). Stale/Ausfall → `unknown`, nie GRÜN (NF-01).
