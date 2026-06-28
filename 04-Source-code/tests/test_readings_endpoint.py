"""Tests fuer GET /v1/readings (DTB-34, FA-03 — Messwert-Historie, T1).

Prueft die Naht gegen die eingefrorene openapi.yaml:
- 200 + Liste von Reading, sortiert nach `order` (Default desc = neueste zuerst),
- Filter `from`/`to`/`sensor_id` + `limit` (behaelt die FRISCHESTEN),
- 400 `Error {code, message}` (NICHT `{detail}`) bei Geschaeftsregel-/Bereichsfehlern
  (`from` nach `to`, ungueltiges `order`, `limit` ausserhalb [1,1000]),
- 503 `Error {code, message}` bei DB-Ausfall (RepositoryError) und nicht bereitem Runtime,
- `Cache-Control: no-store` (Sicherheits-/Echtzeit-Naht, konsistent zur restlichen /v1-API).

DB-frei: ein InMemoryReadingRepository wird ueber `get_runtime` injiziert.
"""

from collections.abc import Generator, Sequence
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.exceptions import RuntimeNotReadyError
from src.api.runtime import get_runtime
from src.main import app
from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.repository import InMemoryReadingRepository, RepositoryError

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def _reading(sensor_id: str, minute: int, temp: float) -> Reading:
    ts = datetime(2026, 6, 23, 10, minute, 0, tzinfo=UTC)
    return Reading(
        sensor_id=sensor_id,
        measured_at=ts,
        received_at=ts,
        surface_temp_c=temp,
        air_temp_c=1.0,
        humidity_pct=80.0,
        source=Source.REAL,
        status=SensorStatus.OK,
    )


def _runtime_with(repo: InMemoryReadingRepository) -> SimpleNamespace:
    return SimpleNamespace(reading_repo=repo)


def _seeded_repo(n: int = 4, sensor_id: str = "anr-rwy-01") -> InMemoryReadingRepository:
    repo = InMemoryReadingRepository()
    for minute in range(n):
        repo.save(_reading(sensor_id, minute, float(minute)))
    return repo


def test_list_readings_returns_seeded_desc_by_default() -> None:
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get("/v1/readings")
    assert resp.status_code == 200
    body = resp.json()
    assert [r["surface_temp_c"] for r in body] == [3.0, 2.0, 1.0, 0.0]
    # Reading-Wire-Form: G2-interne Felder sind Teil des Reading-Schemas.
    assert set(body[0]) >= {"id", "sensor_id", "measured_at", "received_at", "source", "status"}
    assert resp.headers["cache-control"] == "no-store"


def test_list_readings_order_asc() -> None:
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get("/v1/readings", params={"order": "asc"})
    assert resp.status_code == 200
    assert [r["surface_temp_c"] for r in resp.json()] == [0.0, 1.0, 2.0, 3.0]


def test_list_readings_filter_by_sensor_id() -> None:
    repo = InMemoryReadingRepository()
    repo.save(_reading("anr-a", 0, 1.0))
    repo.save(_reading("anr-b", 1, 2.0))
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(repo)
    resp = client.get("/v1/readings", params={"sensor_id": "anr-a"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1 and body[0]["sensor_id"] == "anr-a"


def test_list_readings_filter_from_to_inclusive() -> None:
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get(
        "/v1/readings",
        params={
            "from": "2026-06-23T10:01:00Z",
            "to": "2026-06-23T10:02:00Z",
            "order": "asc",
        },
    )
    assert resp.status_code == 200
    assert [r["surface_temp_c"] for r in resp.json()] == [1.0, 2.0]


def test_list_readings_limit_keeps_newest() -> None:
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get("/v1/readings", params={"limit": 2})
    assert resp.status_code == 200
    assert [r["surface_temp_c"] for r in resp.json()] == [3.0, 2.0]


@pytest.mark.parametrize("valid_limit", [1, 1000])
def test_list_readings_boundary_limit_in_range_returns_200(valid_limit: int) -> None:
    # Gueltige Grenzen [1,1000] muessen 200 liefern (Gegenstueck zu den 400-Out-of-Range-Tests).
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get("/v1/readings", params={"limit": valid_limit})
    assert resp.status_code == 200


def test_list_readings_accepts_naive_datetime_as_utc() -> None:
    # Naiver (Z-loser) Zeitstempel wird als UTC interpretiert (Contract: alle Zeiten UTC) —
    # deckt die naive->UTC-Normalisierung der Naht ab, ohne den Repository-ValueError.
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get(
        "/v1/readings",
        params={"from": "2026-06-23T10:01:00", "to": "2026-06-23T10:02:00", "order": "asc"},
    )
    assert resp.status_code == 200
    assert [r["surface_temp_c"] for r in resp.json()] == [1.0, 2.0]


def test_list_readings_empty_returns_empty_list() -> None:
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(InMemoryReadingRepository())
    resp = client.get("/v1/readings")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_readings_from_after_to_returns_400_contract() -> None:
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get(
        "/v1/readings",
        params={"from": "2026-06-23T11:00:00Z", "to": "2026-06-23T10:00:00Z"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "BAD_REQUEST"
    assert "detail" not in body  # FastAPI-Default {detail} wuerde die eingefrorene Naht brechen
    assert set(body) == {"code", "message"}
    assert resp.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("bad_limit", [0, 1001, 5000])
def test_list_readings_limit_out_of_range_returns_400(bad_limit: int) -> None:
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get("/v1/readings", params={"limit": bad_limit})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "BAD_REQUEST"
    assert "detail" not in body


def test_list_readings_invalid_order_returns_400() -> None:
    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_seeded_repo())
    resp = client.get("/v1/readings", params={"order": "sideways"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "BAD_REQUEST"
    assert "detail" not in body


def test_list_readings_repository_error_returns_503_contract() -> None:
    class _FailingRepo(InMemoryReadingRepository):
        def get_readings(self, **_kwargs: object) -> Sequence[Reading]:
            raise RepositoryError("DB weg")

    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_FailingRepo())
    resp = client.get("/v1/readings")
    assert resp.status_code == 503
    body = resp.json()
    assert body == {"code": "SERVICE_UNAVAILABLE", "message": "G2 momentan nicht lieferfaehig."}
    assert "detail" not in body
    assert resp.headers["cache-control"] == "no-store"


def test_list_readings_repository_value_error_returns_400_contract() -> None:
    # Defense-in-depth: faellt die Repository-Validierung (ValueError) trotz Endpoint-
    # Vorpruefung, bleibt die Naht contract-konform (400 Error), kein rohes 500/{detail}.
    class _ValueErrorRepo(InMemoryReadingRepository):
        def get_readings(self, **_kwargs: object) -> Sequence[Reading]:
            raise ValueError("order muss 'asc' oder 'desc' sein")

    app.dependency_overrides[get_runtime] = lambda: _runtime_with(_ValueErrorRepo())
    resp = client.get("/v1/readings")
    assert resp.status_code == 400
    body = resp.json()
    assert body == {"code": "BAD_REQUEST", "message": "Ungueltige Anfrage."}
    assert "detail" not in body
    assert resp.headers["cache-control"] == "no-store"


def test_list_readings_runtime_not_ready_returns_503_contract() -> None:
    def _not_ready() -> object:
        raise RuntimeNotReadyError("test: runtime fehlt")

    app.dependency_overrides[get_runtime] = _not_ready
    resp = client.get("/v1/readings")
    assert resp.status_code == 503
    body = resp.json()
    assert body == {"code": "SERVICE_UNAVAILABLE", "message": "G2 momentan nicht lieferfaehig."}
    assert "detail" not in body
