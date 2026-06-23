"""Tests fuer den G1-Poller (src/ingest/).

Der Poller bleibt DB-agnostisch und arbeitet gegen das Repository-Interface
aus src/storage/repository.py (Implementierung kommt in DTB-28).
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import httpx
import pytest

from src.ingest.poller import Poller
from src.model.enums import SensorStatus
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
    assert reading.measured_at == datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    assert len(fake_repo.readings) == 1
    assert fake_repo.readings[0].sensor_id == "anr-rwy-01"


def test_poll_missing_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        # surface_temp_c fehlt
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "Pflichtfeld" in caplog.text


def test_poll_out_of_range_temperature_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": 100.0,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "ausserhalb" in caplog.text


def test_poll_out_of_range_humidity_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 101,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "humidity_pct" in caplog.text


def test_poll_http_error_does_not_save(poller: Poller, fake_repo: FakeRepository, caplog) -> None:
    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.side_effect = httpx.HTTPError("Verbindungsfehler")
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "fehlgeschlagen" in caplog.text


def test_poll_invalid_status_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        "status": "broken",
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "status" in caplog.text


def test_poll_non_object_payload_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response([1, 2, 3])
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "kein JSON-Objekt" in caplog.text


def test_poll_invalid_measured_at_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "kein-datum",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Feld ungueltig" in caplog.text


def test_poll_empty_sensor_id_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "   ",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "sensor_id" in caplog.text


def test_poll_pressure_out_of_range_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        "pressure_hpa": 2000,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "pressure_hpa" in caplog.text


def test_poll_non_numeric_optional_pressure_is_failsafe(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    # Fail-safe (NF-01): ein defektes OPTIONALES Feld darf den Poller nicht crashen,
    # sondern muss zu None fuehren (kein Speichern), genau wie bei Pflichtfeldern.
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        "pressure_hpa": "abc",  # nicht-numerisch
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "pressure_hpa" in caplog.text


def test_poll_out_of_range_air_temp_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 99.0,  # ausserhalb -50..50
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "air_temp_c" in caplog.text


def test_poll_measured_at_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": 1234567890,  # kein String
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Feld ungueltig" in caplog.text


def test_poll_measured_at_without_timezone_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00",  # ohne Zeitzone
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Feld ungueltig" in caplog.text


def test_poll_sensor_id_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": 123,  # kein String
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Feld ungueltig" in caplog.text


def test_poll_non_numeric_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": "kalt",  # nicht-numerisch
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Feld ungueltig" in caplog.text


def test_poll_missing_optional_status_defaults_to_ok(
    poller: Poller, fake_repo: FakeRepository
) -> None:
    # Fehlendes optionales status-Feld -> Default OK, Reading wird gespeichert.
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        # kein status-Feld
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.status is SensorStatus.OK
    assert len(fake_repo.readings) == 1


def test_poll_status_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        "status": 123,  # kein String
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "status" in caplog.text
