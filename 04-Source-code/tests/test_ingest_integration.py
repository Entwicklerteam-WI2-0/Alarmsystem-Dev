"""Integrationstest Poller -> Repository (DTB-41, Teil 1).

Belegt die Kette G1-Poll -> Validierung -> Persistenz gegen das ECHTE
InMemoryReadingRepository (statt eines lokalen Fakes wie in test_ingest.py):
poll() speichert ein gueltiges Reading wirklich im Repo und liefert es MIT
vergebener id zurueck (DTB-28-Invariante; bewacht den Poller-Fix gegen Regression).
Fail-safe-Faelle (G1 down, stale, fault, unplausibel) duerfen NICHTS speichern (NF-01).

G1 wird ueber httpx.get gemockt; die Poller-Uhr ist via frozen_now eingefroren,
damit die Stale-Erkennung deterministisch ist. Payloads gemaess
docs/api/v1/g1-consumed.openapi.yaml.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import httpx
import pytest

from src.ingest.poller import Poller
from src.storage.repository import InMemoryReadingRepository

# Gueltiger G1-Snapshot (g1-consumed.openapi.yaml). measured_at 60 s vor frozen_now
# (10:01:00) -> frisch (< stale_timeout 120 s).
_VALID_PAYLOAD = {
    "sensor_id": "anr-rwy-01",
    "measured_at": "2026-06-23T10:00:00Z",
    "surface_temp_c": -0.4,
    "air_temp_c": 1.2,
    "humidity_pct": 96,
    "pressure_hpa": 1013,
    "status": "ok",
}


@pytest.fixture(autouse=True)
def _freeze_poller_clock(frozen_now: datetime, monkeypatch: pytest.MonkeyPatch) -> None:
    # Stale-Erkennung deterministisch: Poller-Uhr auf frozen_now (10:01:00) fixieren.
    monkeypatch.setattr("src.ingest.poller._now", lambda: frozen_now)


def _ok(json_payload: object | None = None) -> Mock:
    response = Mock()
    if json_payload is not None:
        response.json.return_value = json_payload
    response.raise_for_status.return_value = None
    return response


def _error(status_code: int) -> Mock:
    response = Mock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message=f"Server error {status_code}",
        request=Mock(),
        response=Mock(status_code=status_code),
    )
    return response


def _mock_get(current_payload: dict | None = None, *, health_status: int = 200) -> Mock:
    """httpx.get-Mock: beantwortet /health und (bei gesundem /health) /current.

    Bei ungesundem /health darf /current NICHT aufgerufen werden (Fail-safe).
    """

    def side_effect(url: str, **_kwargs: object) -> Mock:
        if url.endswith("/health"):
            return _ok() if health_status == 200 else _error(health_status)
        if url.endswith("/current"):
            if health_status != 200:
                raise AssertionError("/current darf bei ungesundem /health nicht gepollt werden")
            if current_payload is None:
                raise AssertionError("/current wurde nicht erwartet")
            return _ok(current_payload)
        raise ValueError(f"Unbekannte URL: {url}")

    return Mock(side_effect=side_effect)


def test_poll_persists_reading_with_id(
    poller: Poller, reading_repo: InMemoryReadingRepository, sensor_id: str
) -> None:
    # Gutfall: /health ok + gueltiges /current -> Reading landet im echten Repo, der
    # Taupunkt ist berechnet, und poll() liefert das Reading MIT id zurueck (bewacht
    # den Poller-Fix; ohne id braeche der Scheduler-Happy-Path mit ValueError).
    with patch("src.ingest.poller.httpx.get", _mock_get(_VALID_PAYLOAD)):
        reading = poller.poll()

    assert reading is not None
    assert reading.id is not None  # DTB-28-Invariante: persistiert -> id vergeben
    assert reading.dew_point_c is not None  # Magnus-Taupunkt berechnet (DTB-60)
    stored = reading_repo.get_latest(sensor_id)
    assert len(stored) == 1
    assert stored[0].id == reading.id
    assert stored[0].sensor_id == sensor_id


def test_poll_health_down_saves_nothing(
    poller: Poller, reading_repo: InMemoryReadingRepository, sensor_id: str
) -> None:
    # /health 503 -> /current wird nicht gepollt, nichts gespeichert (NF-01).
    mock = _mock_get(health_status=503)
    with patch("src.ingest.poller.httpx.get", mock):
        reading = poller.poll()

    assert reading is None
    assert reading_repo.get_latest(sensor_id) == ()
    assert mock.call_count == 1  # nur /health, kein /current


def test_poll_stale_snapshot_saves_nothing(
    poller: Poller, reading_repo: InMemoryReadingRepository, sensor_id: str
) -> None:
    # measured_at 6 min vor der eingefrorenen Uhr (> stale_timeout) -> verworfen.
    stale = {**_VALID_PAYLOAD, "measured_at": "2026-06-23T09:55:00Z"}
    with patch("src.ingest.poller.httpx.get", _mock_get(stale)):
        reading = poller.poll()

    assert reading is None
    assert reading_repo.get_latest(sensor_id) == ()


def test_poll_fault_snapshot_saves_nothing(
    poller: Poller, reading_repo: InMemoryReadingRepository, sensor_id: str
) -> None:
    # Sensor meldet fault -> Reading verworfen (NF-01, nie GRUEN downstream).
    fault = {**_VALID_PAYLOAD, "status": "fault"}
    with patch("src.ingest.poller.httpx.get", _mock_get(fault)):
        reading = poller.poll()

    assert reading is None
    assert reading_repo.get_latest(sensor_id) == ()


def test_poll_implausible_value_saves_nothing(
    poller: Poller, reading_repo: InMemoryReadingRepository, sensor_id: str
) -> None:
    # Unplausible Oberflaechentemperatur (99 > max_temp_c 50) -> verworfen (NF-05).
    bad = {**_VALID_PAYLOAD, "surface_temp_c": 99}
    with patch("src.ingest.poller.httpx.get", _mock_get(bad)):
        reading = poller.poll()

    assert reading is None
    assert reading_repo.get_latest(sensor_id) == ()
