"""Tests fuer den G1-Poller (src/ingest/).

Der Poller bleibt DB-agnostisch und arbeitet gegen das Repository-Interface
aus src/storage/repository.py (Implementierung kommt in DTB-28).
"""

import json
import logging
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import httpx
import pytest

from src.config.loader import DatenqualitaetSchwellen, PlausibilitaetSchwellen
from src.ingest.poller import Poller
from src.model.schemas import Reading
from src.storage.repository import Repository, RepositoryError


class FakeRepository(Repository):
    """In-Memory-Stub fuer den Poller-Test; erfuellt das Repository-Interface."""

    def __init__(self) -> None:
        self.readings: list[Reading] = []

    def save(self, reading: Reading) -> int:
        self.readings.append(reading)
        return len(self.readings)

    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        # Liefert die neuesten Readings fuer einen Sensor (nach measured_at, absteigend).
        candidates = [r for r in self.readings if r.sensor_id == sensor_id]
        if not candidates:
            return ()
        sorted_candidates = sorted(candidates, key=lambda r: r.measured_at, reverse=True)
        return tuple(sorted_candidates[:limit])

    def get_since(self, sensor_id: str, since: datetime, limit: int = 1000) -> Sequence[Reading]:
        # Liefert Readings eines Sensors seit einem Zeitpunkt (aufsteigend).
        candidates = [
            r for r in self.readings if r.sensor_id == sensor_id and r.measured_at >= since
        ]
        return tuple(sorted(candidates, key=lambda r: r.measured_at)[:limit])


@pytest.fixture
def fake_repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def quality_thresholds() -> DatenqualitaetSchwellen:
    return DatenqualitaetSchwellen(
        stale_timeout_s=120.0,
        max_temp_jump_c_per_min=5.0,
        flatline_timeout_min=15.0,
        flatline_epsilon_c=0.15,
        max_clock_skew_s=5.0,
        min_plausible_dew_point_c=-50.0,
    )


@pytest.fixture
def plausibility_thresholds() -> PlausibilitaetSchwellen:
    return PlausibilitaetSchwellen(
        min_temp_c=-50.0,
        max_temp_c=50.0,
        min_humidity_pct=0.0,
        max_humidity_pct=100.0,
        min_pressure_hpa=800.0,
        max_pressure_hpa=1100.0,
    )


@pytest.fixture(autouse=True)
def frozen_now(request):
    # Deterministische Uhr fuer die Stale-Erkennung: 60 s nach dem measured_at der
    # valid_snapshot-Fixture -> Standard-Snapshots gelten als frisch (< 120 s).
    # Stale-Tests setzen measured_at bewusst weiter in die Vergangenheit.
    # Tests mit @pytest.mark.real_clock laufen gegen die echte Uhr (tz-Awareness-Pruefung).
    if request.node.get_closest_marker("real_clock"):
        yield
        return
    fixed = datetime(2026, 6, 23, 10, 1, 0, tzinfo=UTC)
    with patch("src.ingest.poller._now", return_value=fixed):
        yield


@pytest.fixture
def poller(
    fake_repo: FakeRepository,
    quality_thresholds: DatenqualitaetSchwellen,
    plausibility_thresholds: PlausibilitaetSchwellen,
) -> Poller:
    return Poller(
        base_url="http://g1.test",
        repository=fake_repo,
        data_quality_thresholds=quality_thresholds,
        plausibility_thresholds=plausibility_thresholds,
    )


@pytest.fixture
def valid_snapshot() -> dict:
    """Gueltiger G1-Snapshot als Ausgangsbasis fuer Mutationstests."""
    return {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        "pressure_hpa": 1013,
        "status": "ok",
    }


def _ok_response(json_payload: object | None = None) -> Mock:
    response = Mock()
    if json_payload is not None:
        response.json.return_value = json_payload
    response.raise_for_status.return_value = None
    return response


def _error_response(status_code: int) -> Mock:
    response = Mock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message=f"Server error {status_code}",
        request=Mock(),
        response=Mock(status_code=status_code),
    )
    return response


def _mock_get_for(
    current_payload: dict | None = None,
    current_error: Exception | None = None,
    health_status: int = 200,
    health_error: Exception | None = None,
) -> Mock:
    """Gibt einen Mock zurueck, der /health und /current beantwortet.

    * /health liefert 200 OK, es sei denn health_status != 200 oder health_error ist gesetzt.
    * /current liefert current_payload oder wirft current_error.
    * Wenn /health fehlschlaegt, darf /current nicht aufgerufen werden (Fail-safe).
    """

    def side_effect(url: str, **kwargs) -> Mock:
        if url.endswith("/health"):
            if health_error is not None:
                raise health_error
            if health_status == 200:
                return _ok_response()
            return _error_response(health_status)
        if url.endswith("/current"):
            if health_error is not None or health_status != 200:
                raise RuntimeError(
                    "/current darf bei fehlgeschlagenem /health nicht aufgerufen werden"
                )
            if current_error is not None:
                raise current_error
            if current_payload is None:
                raise RuntimeError("/current wurde nicht erwartet")
            return _ok_response(current_payload)
        raise ValueError(f"Unbekannte URL: {url}")

    return Mock(side_effect=side_effect)


def test_poll_valid_snapshot_saves_reading(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    with patch("src.ingest.poller.httpx.get", _mock_get_for(valid_snapshot)) as mock_get:
        reading = poller.poll()

    assert reading is not None
    assert reading.sensor_id == "anr-rwy-01"
    assert reading.measured_at == datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    assert len(fake_repo.readings) == 1
    assert fake_repo.readings[0].sensor_id == "anr-rwy-01"
    assert mock_get.call_count == 2


def test_poll_missing_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "surface_temp_c": None}
    del snapshot["surface_temp_c"]

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "Pflichtfeld" in caplog.text


def test_poll_out_of_range_temperature_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "surface_temp_c": 100.0}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "surface_temp_c ausserhalb des gueltigen Bereichs: 100.0" in caplog.text


def test_poll_out_of_range_humidity_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "humidity_pct": 101}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "humidity_pct ausserhalb des gueltigen Bereichs: 101.0" in caplog.text


def test_poll_http_error_does_not_save(poller: Poller, fake_repo: FakeRepository, caplog) -> None:
    with patch(
        "src.ingest.poller.httpx.get",
        _mock_get_for(current_error=httpx.HTTPError("Verbindungsfehler")),
    ):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Poll fehlgeschlagen" in caplog.text


def test_poll_5xx_error_does_not_save(poller: Poller, fake_repo: FakeRepository, caplog) -> None:
    with patch("src.ingest.poller.httpx.get", _mock_get_for(current_error=None)) as mock_get:
        # current_payload=None wuerde einen RuntimeError ausloesen; daher mit
        # explizitem _error_response fuer /current bauen.
        def side_effect(url: str, **kwargs) -> Mock:
            if url.endswith("/health"):
                return _ok_response()
            if url.endswith("/current"):
                return _error_response(503)
            raise ValueError(f"Unbekannte URL: {url}")

        mock_get.side_effect = side_effect
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Poll fehlgeschlagen" in caplog.text


def test_poll_invalid_status_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "status": "broken"}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "Ungueltiger status-Wert: 'broken'" in caplog.text


def test_poll_fault_status_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "status": "fault"}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Sensor meldet status=fault" in caplog.text


def test_poll_non_object_payload_does_not_save(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    with patch("src.ingest.poller.httpx.get", _mock_get_for([1, 2, 3])):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "kein JSON-Objekt" in caplog.text


def test_poll_invalid_measured_at_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "measured_at": "kein-datum"}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Feld ungueltig" in caplog.text


def test_poll_non_utc_measured_at_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T10:00:00+02:00"}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "measured_at muss UTC sein" in caplog.text


def test_poll_empty_sensor_id_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "sensor_id": "   "}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "sensor_id darf nicht leer sein" in caplog.text


def test_poll_sensor_id_with_whitespace_is_trimmed(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    snapshot = {**valid_snapshot, "sensor_id": " anr-rwy-01 "}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.sensor_id == "anr-rwy-01"
    assert fake_repo.readings[0].sensor_id == "anr-rwy-01"


def test_poll_pressure_out_of_range_is_set_to_none(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # Fail-safe: ein defektes OPTIONALES Feld darf die Pflicht-Trias nicht blockieren.
    # Out-of-range pressure_hpa wird auf None gesetzt, Reading wird gespeichert.
    snapshot = {**valid_snapshot, "pressure_hpa": 2000}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is not None
    assert reading.pressure_hpa is None
    assert len(fake_repo.readings) == 1
    assert "pressure_hpa ausserhalb des gueltigen Bereichs: 2000.0" in caplog.text


def test_poll_non_numeric_optional_pressure_is_set_to_none(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "pressure_hpa": "abc"}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is not None
    assert reading.pressure_hpa is None
    assert len(fake_repo.readings) == 1
    assert "pressure_hpa muss eine Zahl sein, erhalten: <class 'str'>" in caplog.text


def test_poll_missing_optional_pressure_is_none(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    snapshot = dict(valid_snapshot)
    del snapshot["pressure_hpa"]

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is not None
    assert reading.pressure_hpa is None
    assert len(fake_repo.readings) == 1


def test_poll_optional_pressure_at_boundaries_saves(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    for pressure in (800.0, 1100.0):
        snapshot = {**valid_snapshot, "pressure_hpa": pressure}
        fake_repo.readings.clear()

        with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
            reading = poller.poll()

        assert reading is not None, f"pressure_hpa={pressure} sollte am Grenzwert akzeptiert werden"
        assert reading.pressure_hpa == pressure
        assert len(fake_repo.readings) == 1


def test_poll_out_of_range_air_temp_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "air_temp_c": 99.0}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "air_temp_c ausserhalb des gueltigen Bereichs: 99.0" in caplog.text


@pytest.mark.parametrize("value", [-50.0, 50.0])
def test_poll_temperature_at_boundaries_saves(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, value: float
) -> None:
    snapshot = {**valid_snapshot, "surface_temp_c": value, "air_temp_c": value}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is not None
    assert reading.surface_temp_c == value
    assert reading.air_temp_c == value
    assert len(fake_repo.readings) == 1


@pytest.mark.parametrize("value", [0.0, 100.0])
def test_poll_humidity_at_boundaries_saves(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, value: float
) -> None:
    snapshot = {**valid_snapshot, "humidity_pct": value}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is not None
    assert reading.humidity_pct == value
    assert len(fake_repo.readings) == 1


def test_poll_uses_configured_plausibility_thresholds(
    fake_repo: FakeRepository,
    quality_thresholds: DatenqualitaetSchwellen,
    valid_snapshot: dict,
) -> None:
    # NF-05: Plausibilitaets-Grenzen muessen aus der Config kommen, nicht hardgecoded sein.
    # Wenn wir die Grenzen verschärfen, wird ein vorher gueltiger Wert verworfen.
    strict_plausibility = PlausibilitaetSchwellen(
        min_temp_c=-10.0,
        max_temp_c=10.0,
        min_humidity_pct=0.0,
        max_humidity_pct=100.0,
        min_pressure_hpa=800.0,
        max_pressure_hpa=1100.0,
    )
    poller = Poller(
        base_url="http://g1.test",
        repository=fake_repo,
        data_quality_thresholds=quality_thresholds,
        plausibility_thresholds=strict_plausibility,
    )
    snapshot = {**valid_snapshot, "surface_temp_c": 20.0}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0


def test_poll_measured_at_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "measured_at": 1234567890}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "measured_at muss ein String sein" in caplog.text


def test_poll_measured_at_without_timezone_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T10:00:00"}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "measured_at muss UTC sein" in caplog.text


def test_poll_sensor_id_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "sensor_id": 123}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "sensor_id muss ein String sein" in caplog.text


def test_poll_non_numeric_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "surface_temp_c": "kalt"}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "surface_temp_c muss eine Zahl sein, erhalten: <class 'str'>" in caplog.text


@pytest.mark.parametrize("field", ["surface_temp_c", "air_temp_c", "humidity_pct"])
def test_poll_nan_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, field: str
) -> None:
    snapshot = {**valid_snapshot, field: math.nan}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0


@pytest.mark.parametrize("field", ["surface_temp_c", "air_temp_c", "humidity_pct"])
def test_poll_inf_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, field: str
) -> None:
    snapshot = {**valid_snapshot, field: math.inf}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0


def test_poll_missing_status_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # status ist Pflichtfeld laut G1-Contract; fehlendes Feld darf nicht still
    # auf OK defaulten -> Fail-safe verworfen (NF-01).
    snapshot = dict(valid_snapshot)
    del snapshot["status"]

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "Pflichtfeld in G1-Antwort fehlt: status" in caplog.text


def test_poll_status_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "status": 123}

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "status muss ein String sein, erhalten: <class 'int'>" in caplog.text


def test_poll_non_json_response_is_failsafe(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    with patch("src.ingest.poller.httpx.get", _mock_get_for()) as mock_get:

        def side_effect(url: str, **kwargs) -> Mock:
            if url.endswith("/health"):
                return _ok_response()
            if url.endswith("/current"):
                return response
            raise ValueError(f"Unbekannte URL: {url}")

        mock_get.side_effect = side_effect
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Antwort nicht als JSON parsierbar" in caplog.text


def test_poll_repository_error_is_failsafe(
    caplog,
    quality_thresholds: DatenqualitaetSchwellen,
    plausibility_thresholds: PlausibilitaetSchwellen,
) -> None:
    class RaisingRepository(Repository):
        def save(self, reading: Reading) -> int:
            raise RepositoryError("DB nicht erreichbar")

        def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
            raise RepositoryError("DB nicht erreichbar")

        def get_since(
            self, sensor_id: str, since: datetime, limit: int = 1000
        ) -> Sequence[Reading]:
            raise RepositoryError("DB nicht erreichbar")

    repo = RaisingRepository()
    poller = Poller(
        base_url="http://g1.test",
        repository=repo,
        data_quality_thresholds=quality_thresholds,
        plausibility_thresholds=plausibility_thresholds,
    )
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        "status": "ok",
    }

    with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
        reading = poller.poll()

    assert reading is None
    assert "Speichern des Readings fehlgeschlagen" in caplog.text


def test_poll_unexpected_repository_error_is_not_swallowed(
    caplog,
    quality_thresholds: DatenqualitaetSchwellen,
    plausibility_thresholds: PlausibilitaetSchwellen,
) -> None:
    # Nur RepositoryError soll fail-safe abgefangen werden; andere Exceptions
    # muessen hochgereicht werden, um Programmierfehler nicht zu verschleiern.
    class BuggyRepository(Repository):
        def save(self, reading: Reading) -> int:
            raise RuntimeError("unerwarteter Bug")

        def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
            return ()

        def get_since(
            self, sensor_id: str, since: datetime, limit: int = 1000
        ) -> Sequence[Reading]:
            return ()

    poller = Poller(
        base_url="http://g1.test",
        repository=BuggyRepository(),
        data_quality_thresholds=quality_thresholds,
        plausibility_thresholds=plausibility_thresholds,
    )
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
        "status": "ok",
    }

    with pytest.raises(RuntimeError, match="unerwarteter Bug"):
        with patch("src.ingest.poller.httpx.get", _mock_get_for(snapshot)):
            poller.poll()


# -----------------------------------------------------------------------------
# Stale-Erkennung + Clock-Skew (DTB-58)
# -----------------------------------------------------------------------------
def test_poll_stale_snapshot_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # measured_at liegt 6 min vor der eingefrorenen Uhr (> 120 s) -> stale -> verwerfen
    # (FA-04, NF-01: keine veralteten Werte als aktuell speichern/GRUEN ausgeben).
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T09:55:00Z"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "veraltet" in caplog.text


def test_poll_snapshot_at_freshness_boundary_saves(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    # Grenze: measured_at genau 120 s vor der eingefrorenen Uhr (10:01:00) -> age == 120 s.
    # Wegen strikter "> 120 s"-Semantik gilt das noch als frisch -> gespeichert.
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T09:59:00Z"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert len(fake_repo.readings) == 1


def test_poll_snapshot_just_over_boundary_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # Grenze + 1 s: 121 s alt -> stale -> verworfen. Sichert die "> 120"-Kante gegen Regression.
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T09:58:59Z"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "veraltet" in caplog.text


def test_poll_future_timestamp_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # measured_at liegt 60 s in der Zukunft (defekte/falsch gestellte G1-Uhr) -> unplausibel
    # -> fail-safe verworfen (NF-01; Schwellenwerte.md §3 unplausibler Wert).
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T10:02:00Z"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "Zukunft" in caplog.text


def test_poll_minor_clock_skew_still_saves(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    # Kleiner Vorlauf (3 s in der Zukunft, innerhalb der Skew-Toleranz) ist
    # normale Uhren-Drift -> gespeichert.
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T10:01:03Z"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert len(fake_repo.readings) == 1


def test_poll_clock_skew_exactly_at_limit_saves(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    # Genau am Limit (5 s in der Zukunft) -> noch akzeptiert.
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T10:01:05Z"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert len(fake_repo.readings) == 1


def test_poll_clock_skew_just_over_limit_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # 5,001 s in der Zukunft -> ueber der Toleranz -> verworfen.
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T10:01:05.001Z"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "Zukunft" in caplog.text


@pytest.mark.real_clock
def test_now_is_timezone_aware() -> None:
    # _now() muss tz-aware (UTC) liefern; sonst schlaegt die Subtraktion mit measured_at
    # (tz-aware) als TypeError fehl. Laeuft bewusst gegen die echte Uhr (kein frozen_now).
    from src.ingest.poller import _now

    assert _now().tzinfo is not None


# -----------------------------------------------------------------------------
# Taupunkt-Integration (DTB-60)
# -----------------------------------------------------------------------------
def test_poll_computes_dew_point(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    # DTB-60: Poller berechnet dew_point_c (Magnus) und fuellt es ins Reading.
    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(valid_snapshot)
        reading = poller.poll()

    # Referenz: Magnus(a=17,62; b=243,12; Schwellenwerte.md §1) fuer T_a=1,2 °C, RH=96 %
    # ergibt T_d = 0,6325 °C (unabhaengig nachgerechnet, nicht aus der Implementierung).
    assert reading is not None
    assert reading.dew_point_c == pytest.approx(0.63, abs=1e-2)
    # dew_point_c muss auch persistiert sein, nicht nur im Returnwert stehen.
    assert len(fake_repo.readings) == 1
    assert fake_repo.readings[0].dew_point_c == pytest.approx(0.63, abs=1e-2)


def test_poll_computes_negative_dew_point_in_frost(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    # Use-Case-Kern (Frost): bei Minustemperaturen muss ein negativer Taupunkt
    # korrekt ins Reading geschrieben werden. Magnus(-5 °C, 80 %) = -7,92 °C.
    snapshot = {**valid_snapshot, "surface_temp_c": -6.0, "air_temp_c": -5.0, "humidity_pct": 80}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.dew_point_c == pytest.approx(-7.92, abs=1e-2)


def test_poll_dew_point_none_when_humidity_zero(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # Fail-safe (Entscheidungslog DTB-32): RH=0 laesst T_d nicht berechnen ->
    # calculate_dew_point wirft ValueError -> Poller faengt ihn -> dew_point_c=None.
    # Das Reading wird trotzdem gespeichert (kein Crash, kein stilles GRUEN downstream).
    snapshot = {**valid_snapshot, "humidity_pct": 0}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.dew_point_c is None
    assert len(fake_repo.readings) == 1
    assert "Taupunkt nicht berechenbar" in caplog.text
    # Degradiert (Reading bleibt erhalten) -> WARNING, nicht ERROR (kein Verwerfen).
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_poll_dew_point_none_when_humidity_near_zero(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # H1-Regression: RH knapp ueber 0 liefert einen absurden Taupunkt (< -50 °C).
    # Der Poller plausibilisiert das Ergebnis und setzt dew_point_c=None, statt einen
    # unsinnigen Wert zu speichern, der downstream faelschlich GRUEN ausloesen koennte.
    snapshot = {**valid_snapshot, "humidity_pct": 0.01}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.dew_point_c is None
    assert len(fake_repo.readings) == 1
    assert "unplausibel" in caplog.text
    # Degradiert (Reading bleibt erhalten) -> WARNING, nicht ERROR (kein Verwerfen).
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_poll_keeps_dew_point_at_plausibility_floor(
    poller: Poller,
    fake_repo: FakeRepository,
    valid_snapshot: dict,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    # Grenzfall (strict <): ein Taupunkt GENAU auf der konfigurierten Untergrenze ist noch
    # plausibel und wird behalten (nur Werte echt darunter -> None, s. near_zero-Test).
    floor = quality_thresholds.min_plausible_dew_point_c
    with patch("src.ingest.poller.calculate_dew_point", return_value=floor):
        with patch("src.ingest.poller.httpx.get") as mock_get:
            mock_get.return_value = _ok_response(valid_snapshot)
            reading = poller.poll()

    assert reading is not None
    assert reading.dew_point_c == floor
    assert fake_repo.readings[0].dew_point_c == floor


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_poll_dew_point_non_finite_is_none(
    poller: Poller,
    fake_repo: FakeRepository,
    valid_snapshot: dict,
    caplog,
    bad_value: float,
) -> None:
    # Defense-in-depth: sollte calculate_dew_point silent NaN/Inf durchreichen,
    # wird dew_point_c=None und das Reading trotzdem gespeichert (NF-01).
    with patch("src.ingest.poller.calculate_dew_point", return_value=bad_value):
        with patch("src.ingest.poller.httpx.get") as mock_get:
            mock_get.return_value = _ok_response(valid_snapshot)
            reading = poller.poll()

    assert reading is not None
    assert reading.dew_point_c is None
    assert len(fake_repo.readings) == 1
    assert "nicht endlich" in caplog.text


# -----------------------------------------------------------------------------
# Typ-Validierung (DTB-22/Review-Blocker)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("field", ["surface_temp_c", "air_temp_c", "humidity_pct"])
def test_poll_bool_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, field: str, caplog
) -> None:
    # bool ist in Python ein int-Subtyp und wuerde stumm zu 0.0/1.0 -> gefaehrlich.
    snapshot = {**valid_snapshot, field: True}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "bool" in caplog.text


def test_poll_bool_optional_pressure_is_set_to_none(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # Auch optionale Zahlenfelder duerfen kein bool akzeptieren.
    snapshot = {**valid_snapshot, "pressure_hpa": False}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.pressure_hpa is None
    assert len(fake_repo.readings) == 1
    assert "bool" in caplog.text


# ---------------------------------------------------------------------------
# DTB-59: G1 Health-Check vor /current
# ---------------------------------------------------------------------------


def test_poll_health_503_does_not_poll_current(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    with patch(
        "src.ingest.poller.httpx.get",
        _mock_get_for(health_status=503),
    ) as mock_get:
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert mock_get.call_count == 1
    assert "G1-Health-Check fehlgeschlagen" in caplog.text


def test_poll_health_http_error_does_not_poll_current(
    poller: Poller, fake_repo: FakeRepository, caplog
) -> None:
    with patch(
        "src.ingest.poller.httpx.get",
        _mock_get_for(health_error=httpx.HTTPError("Verbindungsfehler")),
    ) as mock_get:
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert mock_get.call_count == 1
    assert "G1-Health-Check fehlgeschlagen" in caplog.text


def test_poll_health_ok_then_current_saves(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    with patch(
        "src.ingest.poller.httpx.get",
        _mock_get_for(valid_snapshot),
    ) as mock_get:
        reading = poller.poll()

    assert reading is not None
    assert len(fake_repo.readings) == 1
    assert mock_get.call_count == 2
