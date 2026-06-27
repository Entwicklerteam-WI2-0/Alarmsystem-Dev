"""Tests fuer GET /v1/health (P0.3 / Contract v1: 200 Health, 503 Error).

Der Endpoint ist eine Liveness-Probe (openapi.yaml: ``200`` = erreichbar,
``503`` = (noch) nicht lieferfaehig). Solange der DI-/Runtime-Graph (lifespan)
nicht steht, ist G2 nicht lieferfaehig -> ``503`` mit dem Contract-Fehlerformat
``Error {code, message}`` (NICHT FastAPIs ``{detail}``). Steht der Runtime ->
``200`` ``Health {status: "ok"}``.

get_runtime wird via ``app.dependency_overrides`` gesteuert (kein DB, kein
Lifespan) — analog zu den /v1/assessment/current-Tests.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app, get_runtime

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Jeder Test setzt seine eigene Runtime-Annahme; danach aufraeumen."""
    yield
    app.dependency_overrides.clear()


def test_health_ready_returns_200_and_status_ok():
    # Arrange: Runtime-Graph steht -> get_runtime liefert ein (beliebiges) Objekt.
    # Der Endpoint nutzt den Wert nicht, nur die Readiness (kein Raise).
    app.dependency_overrides[get_runtime] = lambda: object()

    # Act
    response = client.get("/v1/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


def test_health_not_ready_returns_503_error_envelope():
    # Arrange: kein Override + keine Lifespan (module-level TestClient laeuft ohne
    # Context-Manager) -> app.state.runtime fehlt -> get_runtime-Guard greift.

    # Act
    response = client.get("/v1/health")

    # Assert: Contract-Fehlerformat (nur code+message), nie rohes 500/{detail},
    # nicht cachebar (sonst veralteter Ausfall-Zustand hinter einem Proxy).
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body.keys()) == {"code", "message"}
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert isinstance(body["message"], str) and body["message"]
