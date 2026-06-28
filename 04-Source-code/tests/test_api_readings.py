"""Tests fuer GET /v1/readings (DTB-34, FA-03).

Prueft: Historien-Endpoint liefert Readings aus dem ReadingRepository im Zeitfenster,
unterstuetzt Pagination (limit/offset) und Sortierung, validiert Query-Parameter und
bleibt bei Persistenzfehlern/Nicht-Verfuegbarkeit fail-safe (503 im Contract-Format).
"""

from collections.abc import Generator
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
def _clear_overrides() -> Generator[None, None, None]:
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
    for key, value in NO_STORE_HEADERS.items():
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


def test_get_readings_naive_timestamp_returns_400(
    reading_repo: InMemoryReadingRepository,
) -> None:
    # Naive datetime ohne Timezone-Offset ('Z' fehlt) -> Pydantic parst naive datetime
    # -> _validate_get_between_args raised ValueError -> 400 (LOW-Review-Finding DTB-34:
    # Regressionsschutz fuer den naive-Zeitstempel-Pfad).
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings", params={"from": "2026-06-23T10:00:00"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "BAD_REQUEST"
    assert "from" in body["message"]
    assert "detail" not in body


def test_get_readings_non_utc_timestamp_returns_400(
    reading_repo: InMemoryReadingRepository,
) -> None:
    # Zeitzonenbewusst, aber NICHT UTC ('+05:30'): PyMySQL serialisiert die Wall-Clock
    # und ignoriert den Offset -> auf DB-Ebene falsches Zeitfenster (DTB-34 Review MEDIUM).
    # Muss daher 400 sein, nicht 200-mit-falschen-Daten.
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings", params={"from": "2026-06-23T10:00:00+05:30"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "BAD_REQUEST"
    assert "from" in body["message"]
    assert "detail" not in body


def test_get_readings_unexpected_mapping_error_returns_503(
    reading_repo: InMemoryReadingRepository,
) -> None:
    # MEDIUM-Review-Finding DTB-34: Schluege das Domain->Wire-Mapping unerwartet fehl,
    # darf KEIN roher 500 mit {detail: ...} austreten — der Endpoint faengt es fail-safe
    # als 503 im Contract-Format ab. In Pydantic v2 IST ValidationError eine Subklasse
    # von ValueError -> deshalb steht `except ValidationError` im Endpoint VOR
    # `except ValueError`, damit dieser serverseitige Drift als 503 (nicht als 400) endet.
    # Ein Stub liefert ein Objekt, dessen model_dump() das ReadingResponse-Schema
    # verletzt (leeres dict -> Pflichtfelder fehlen -> ValidationError).
    def _drifted_repo(*args: object, **kwargs: object) -> list[object]:
        return [SimpleNamespace(model_dump=lambda: {})]

    reading_repo.get_between = _drifted_repo  # type: ignore[method-assign]
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings")

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert "detail" not in body


def test_get_readings_unexpected_runtime_error_returns_503(
    reading_repo: InMemoryReadingRepository,
) -> None:
    # Letzter Fail-safe (DTB-34): eine unerwartete Ausnahme, die WEDER ValueError/
    # ValidationError NOCH RepositoryError ist (hier TypeError aus model_dump), darf
    # keinen rohen 500 mit {detail: ...} austreten lassen -> 503 im Contract-Format.
    def _boom_model_dump() -> dict[str, object]:
        raise TypeError("simulierter unerwarteter Mapping-Crash")

    def _drifted_repo(*args: object, **kwargs: object) -> list[object]:
        return [SimpleNamespace(model_dump=_boom_model_dump)]

    reading_repo.get_between = _drifted_repo  # type: ignore[method-assign]
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings")

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert "detail" not in body


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


def test_get_readings_invalid_order_returns_400_contract(
    reading_repo: InMemoryReadingRepository,
) -> None:
    """Ungueltiger `order`-Wert muss 400 im Contract-Format liefern, nicht 422/detail."""
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings", params={"order": "invalid"})

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "BAD_REQUEST"
    assert "detail" not in body


def test_get_readings_empty_result_returns_200_empty_list(
    reading_repo: InMemoryReadingRepository,
) -> None:
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings")

    assert resp.status_code == 200
    assert resp.json() == []
    _assert_no_store_header(resp)


def test_get_readings_offset_beyond_total_returns_empty_list(
    reading_repo: InMemoryReadingRepository,
) -> None:
    reading_repo.save(_make_reading("anr-rwy-01", datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC), 1.0))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(reading_repo=reading_repo)

    resp = client.get("/v1/readings", params={"offset": 10})

    assert resp.status_code == 200
    assert resp.json() == []


def test_get_readings_limit_at_max_returns_200(
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

    resp = client.get("/v1/readings", params={"limit": 1000})

    assert resp.status_code == 200
    assert len(resp.json()) == 5
