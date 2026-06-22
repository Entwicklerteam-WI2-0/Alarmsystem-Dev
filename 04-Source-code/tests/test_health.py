"""Test für den Health-Endpoint (P0.3, DoD: GET /health -> 200)."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_returns_200_and_status_ok():
    # Act
    response = client.get("/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
