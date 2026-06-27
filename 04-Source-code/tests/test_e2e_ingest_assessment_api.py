"""E2E-Test Ingest -> Bewertung -> API (DTB-41).

Schliesst die Kette ueber den echten Pipeline-Pfad, so wie der Scheduler ihn faehrt:
    poller.poll()  (G1 gemockt, echtes InMemoryReadingRepository)
      -> service.assess_reading(reading, now)   (direkt, KEIN Re-Load via get_latest;
         ein Re-Load wuerde den Poller-id-Fix maskieren)
      -> GET /v1/assessment/current             (liest das Reading selbst via get_latest)

Repos sind In-Memory (runtime-Fixture), G1 ist gemockt, der Endpoint wird ueber eine
separate TestClient-Instanz + dependency_overrides[get_runtime] angesprochen (keine
DB, kein Lifespan, kein Scheduler).

Zeit: BEWUSST echte Wall-Clock-Zeit (kein frozen_now). Der Endpoint prueft die
Aktualitaet zur Serve-Zeit erneut mit datetime.now(UTC) (main.py); ein eingefrorener
Vergangenheits-Zeitstempel waere dort stale -> unknown statt green. Der Happy-Path
muss daher relativ zur realen Uhr frisch sein.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import Runtime, app, get_runtime

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_overrides_and_state():
    # try/finally: bei Fehler im Test keine Override-/State-Leaks (sonst koennte der
    # reihenfolgeabhaengige test_current_runtime_not_initialized_returns_503 brechen).
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "runtime"):
            del app.state.runtime


def _ok(json_payload: object | None = None) -> Mock:
    response = Mock()
    if json_payload is not None:
        response.json.return_value = json_payload
    response.raise_for_status.return_value = None
    return response


def _mock_get(current_payload: dict | None, *, healthy: bool = True) -> Mock:
    def side_effect(url: str, **_kwargs: object) -> Mock:
        if url.endswith("/health"):
            if healthy:
                return _ok()
            raise httpx.HTTPStatusError(
                message="Service Unavailable", request=Mock(), response=Mock(status_code=503)
            )
        if url.endswith("/current"):
            assert healthy, "/current darf bei ungesundem /health nicht gepollt werden"
            return _ok(current_payload)
        raise ValueError(f"Unbekannte URL: {url}")

    return Mock(side_effect=side_effect)


def _green_payload(measured_at: datetime) -> dict:
    # GREEN-Kaskade (Schwellenwerte.md §2): T_s=5.0 (>gelb_auffang 1.0), Taupunkt aus
    # air_temp_c=5.0 + RH=50 % ~ -4.6 °C -> delta_t ~ 9.6 (>feucht 1.0) -> trocken -> GRUEN.
    return {
        "sensor_id": "anr-rwy-01",
        "measured_at": measured_at.isoformat(),
        "surface_temp_c": 5.0,
        "air_temp_c": 5.0,
        "humidity_pct": 50,
        "pressure_hpa": 1013,
        "status": "ok",
    }


def test_poll_to_current_endpoint_happy_path(runtime: Runtime) -> None:
    now = datetime.now(UTC)

    # 1.+2. G1 gesund + gueltiger Snapshot -> Poller persistiert ins echte Repo.
    with patch("src.ingest.poller.httpx.get", _mock_get(_green_payload(now))):
        reading = runtime.poller.poll()
    assert reading is not None
    assert reading.id is not None  # persistiert (DTB-28-Invariante)

    # 3. Bewertung direkt aus dem poll()-Ergebnis (wie der Scheduler; kein Re-Load).
    assessment = runtime.service.assess_reading(reading, now)
    assert assessment.id is not None

    # 4.+5. Endpoint liest Reading + Assessment selbst aus dem geteilten Runtime.
    app.dependency_overrides[get_runtime] = lambda: runtime
    response = client.get("/v1/assessment/current")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["risk_level"] == "green"
    assert body["is_stale"] is False
    assert body["sensor_status"] == "ok"
    assert body["measured_at"] is not None
    assert body["assessed_at"] is not None
    assert body["surface_temp_c"] == 5.0


def test_no_data_returns_503(runtime: Runtime) -> None:
    now = datetime.now(UTC)

    # /health 503 -> poll() = None -> Service speichert ein unknown-Assessment, aber
    # KEIN Reading -> der Endpoint hat kein Reading -> 503 (Contract: nicht lieferfaehig).
    with patch("src.ingest.poller.httpx.get", _mock_get(None, healthy=False)):
        reading = runtime.poller.poll()
    assert reading is None
    runtime.service.assess_reading(reading, now)  # unknown-Assessment, ohne Reading

    app.dependency_overrides[get_runtime] = lambda: runtime
    response = client.get("/v1/assessment/current")

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body.keys()) == {"code", "message"}  # nie green, nie {detail}
    assert body["code"] == "SERVICE_UNAVAILABLE"
