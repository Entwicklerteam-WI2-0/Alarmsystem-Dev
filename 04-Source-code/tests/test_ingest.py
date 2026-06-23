"""Tests fuer den G1-Poller (src/ingest/).

Der Poller bleibt DB-agnostisch und arbeitet gegen das Repository-Interface
aus src/storage/repository.py (Implementierung kommt in DTB-28).
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from src.ingest.poller import Poller
from src.model.schemas import Reading
from src.storage.repository import Repository


class FakeRepository(Repository):
    """In-Memory-Stub fuer den Poller-Test; erfuellt das Repository-Interface."""

    def __init__(self) -> None:
        self.readings: list[Reading] = []

    def save(self, reading: Reading) -> int:
        self.readings.append(reading)
        return len(self.readings)


@pytest.fixture
def fake_repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def poller(fake_repo: FakeRepository) -> Poller:
    return Poller(base_url="http://g1.test", repository=fake_repo)


def _ok_response(snapshot: dict) -> Mock:
    response = Mock()
    response.json.return_value = snapshot
    response.raise_for_status.return_value = None
    return response


def test_poll_valid_snapshot_saves_reading(poller: Poller, fake_repo: FakeRepository) -> None:
    # Arrange
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        "pressure_hpa": 1013,
        "status": "ok",
    }

    # Act
    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    # Assert
    assert reading is not None
    assert reading.sensor_id == "anr-rwy-01"
    assert reading.measured_at == datetime(2026, 6, 23, 10, 0, 0, tzinfo=timezone.utc)
    assert len(fake_repo.readings) == 1
    assert fake_repo.readings[0].sensor_id == "anr-rwy-01"
