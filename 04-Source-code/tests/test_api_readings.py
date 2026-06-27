"""Tests fuer GET /v1/readings (DTB-34, FA-03).

Prueft: Historien-Endpoint liefert Readings aus dem ReadingRepository im Zeitfenster,
unterstuetzt Pagination (limit/offset) und Sortierung, validiert Query-Parameter und
bleibt bei Persistenzfehlern/Nicht-Verfuegbarkeit fail-safe (503 im Contract-Format).
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.exceptions import RuntimeNotReadyError
from src.api.responses import NO_STORE_HEADERS
from src.api.runtime import get_runtime
from src.main import app
from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading, ReadingResponse
from src.storage.repository import InMemoryReadingRepository, RepositoryError

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> None:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def reading_repo() -> InMemoryReadingRepository:
    return InMemoryReadingRepository()


def _make_reading(sensor_id: str, measured_at: datetime, surface_temp_c: float = 0.0) -> Reading:
    return Reading(
        sensor_id=sensor_id,
        measured_at=measured_at,
        received_at=measured_at,
        surface_temp_c=surface_temp_c,
        air_temp_c=1.0,
        humidity_pct=80.0,
        source=Source.REAL,
        status=SensorStatus.OK,
    )


def _assert_no_store_header(resp: object) -> None:
    key, value = next(iter(NO_STORE_HEADERS.items()))
    assert resp.headers[key.lower()] == value


def test_get_readings_returns_history_with_default_sensor(
    reading_repo: InMemoryReadingRepository,
) -> None:
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC), 1.0))
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 5, 0, tzinfo=UTC), 2.0))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["surface_temp_c"] == pytest.approx(2.0)
    assert body[1]["surface_temp_c"] == pytest.approx(1.0)
    _assert_no_store_header(resp)


def test_get_readings_filters_by_time_window(
    reading_repo: InMemoryReadingRepository,
) -> None:
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 9, 55, 0, tzinfo=UTC), 1.0))
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC), 2.0))
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 5, 0, tzinfo=UTC), 3.0))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get(
        "/v1/readings",
        params={
            "from": "2026-06-23T09:58:00Z",
            "to": "2026-06-23T10:03:00Z",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["surface_temp_c"] == pytest.approx(2.0)


def test_get_readings_ascending_order(
    reading_repo: InMemoryReadingRepository,
) -> None:
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC), 1.0))
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 5, 0, tzinfo=UTC), 2.0))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings", params={"order": "asc"})

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["surface_temp_c"] == pytest.approx(1.0)
    assert body[1]["surface_temp_c"] == pytest.approx(2.0)


def test_get_readings_pagination(
    reading_repo: InMemoryReadingRepository,
) -> None:
    for minute in range(5):
        reading_repo.save(
            _make_reading(
                "anr-rwy-01",
                datetime(2026, 6, 23, 10, minute, 0, tzinfo=UTC),
                float(minute),
            )
        )
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings", params={"limit": 2, "offset": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["surface_temp_c"] == pytest.approx(3.0)
    assert body[1]["surface_temp_c"] == pytest.approx(2.0)


def test_get_readings_filter_by_sensor_id(
    reading_repo: InMemoryReadingRepository,
) -> None:
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC), 1.0))
    reading_repo.save(_make_reading("anr-rwy-02", datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC), 2.0))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings", params={"sensor_id": "anr-rwy-02"})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["surface_temp_c"] == pytest.approx(2.0)


def test_get_readings_from_after_to_returns_400(
    reading_repo: InMemoryReadingRepository,
) -> None:
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get(
        "/v1/readings",
        params={
            "from": "2026-06-23T11:00:00Z",
            "to": "2026-06-23T10:00:00Z",
        },
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "BAD_REQUEST"


def test_get_readings_runtime_not_ready_returns_503_contract() -> None:
    def _not_ready() -> object:
        raise RuntimeNotReadyError("test: runtime fehlt")

    app.dependency_overrides[get_runtime] = _not_ready

    resp = client.get("/v1/readings")

    assert resp.status_code == 503
    body = resp.json()
    assert body == {"code": "SERVICE_UNAVAILABLE", "message": "G2 momentan nicht lieferfaehig."}
    assert "detail" not in body
    _assert_no_store_header(resp)


def test_get_readings_repository_error_returns_503(
    reading_repo: InMemoryReadingRepository,
) -> None:
    def _failing_repo(*args: object, **kwargs: object) -> object:
        raise RepositoryError("DB nicht erreichbar")

    reading_repo.get_between = _failing_repo  # type: ignore[method-assign]
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings")

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert "detail" not in body


def test_get_readings_response_matches_reading_response_schema(
    reading_repo: InMemoryReadingRepository,
) -> None:
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC), 1.0))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    parsed = ReadingResponse.model_validate(body[0])
    assert parsed.id is not None
    assert parsed.sensor_id == "anr-rwy-01"
    assert parsed.surface_temp_c == pytest.approx(1.0)
