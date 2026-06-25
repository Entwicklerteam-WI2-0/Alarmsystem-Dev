"""Tests fuer den G1-Poller (src/ingest/).

Der Poller bleibt DB-agnostisch und arbeitet gegen das Repository-Interface
aus src/storage/repository.py (Implementierung kommt in DTB-28).
"""

import json
import logging
import math
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import httpx
import pytest

from src.ingest.poller import MIN_PLAUSIBLE_DEW_POINT_C, Poller
from src.model.enums import SensorStatus
from src.model.schemas import Reading
from src.storage.repository import Repository, RepositoryError


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


@pytest.fixture(autouse=True)
def frozen_now():
    # Deterministische Uhr fuer die Stale-Erkennung: 60 s nach dem measured_at der
    # valid_snapshot-Fixture -> Standard-Snapshots gelten als frisch (< 120 s).
    # Stale-Tests setzen measured_at bewusst weiter in die Vergangenheit.
    fixed = datetime(2026, 6, 23, 10, 1, 0, tzinfo=UTC)
    with patch("src.ingest.poller._now", return_value=fixed):
        yield


def _ok_response(snapshot: dict) -> Mock:
    response = Mock()
    response.json.return_value = snapshot
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


def test_poll_valid_snapshot_saves_reading(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(valid_snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.sensor_id == "anr-rwy-01"
    assert reading.measured_at == datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    assert len(fake_repo.readings) == 1
    assert fake_repo.readings[0].sensor_id == "anr-rwy-01"


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


def test_poll_missing_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "surface_temp_c": None}
    del snapshot["surface_temp_c"]

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "Pflichtfeld" in caplog.text


def test_poll_out_of_range_temperature_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "surface_temp_c": 100.0}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "surface_temp_c ausserhalb des gueltigen Bereichs: 100.0" in caplog.text


def test_poll_out_of_range_humidity_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "humidity_pct": 101}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "humidity_pct ausserhalb des gueltigen Bereichs: 101.0" in caplog.text


def test_poll_http_error_does_not_save(poller: Poller, fake_repo: FakeRepository, caplog) -> None:
    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.side_effect = httpx.HTTPError("Verbindungsfehler")
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Poll fehlgeschlagen" in caplog.text


def test_poll_5xx_error_does_not_save(poller: Poller, fake_repo: FakeRepository, caplog) -> None:
    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _error_response(503)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Poll fehlgeschlagen" in caplog.text


def test_poll_invalid_status_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "status": "broken"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "Ungueltiger status-Wert: 'broken'" in caplog.text


def test_poll_fault_status_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "status": "fault"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Sensor meldet status=fault" in caplog.text


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
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "measured_at": "kein-datum"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Feld ungueltig" in caplog.text


def test_poll_non_utc_measured_at_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T10:00:00+02:00"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "measured_at muss UTC sein" in caplog.text


def test_poll_empty_sensor_id_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "sensor_id": "   "}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "sensor_id darf nicht leer sein" in caplog.text


def test_poll_pressure_out_of_range_is_set_to_none(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    # Fail-safe: ein defektes OPTIONALES Feld darf die Pflicht-Trias nicht blockieren.
    # Out-of-range pressure_hpa wird auf None gesetzt, Reading wird gespeichert.
    snapshot = {**valid_snapshot, "pressure_hpa": 2000}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.pressure_hpa is None
    assert len(fake_repo.readings) == 1
    assert "pressure_hpa ausserhalb des gueltigen Bereichs: 2000.0" in caplog.text


def test_poll_non_numeric_optional_pressure_is_set_to_none(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "pressure_hpa": "abc"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.pressure_hpa is None
    assert len(fake_repo.readings) == 1
    assert "pressure_hpa muss eine Zahl sein, erhalten: 'abc'" in caplog.text


def test_poll_missing_optional_pressure_is_none(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    snapshot = dict(valid_snapshot)
    del snapshot["pressure_hpa"]

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
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

        with patch("src.ingest.poller.httpx.get") as mock_get:
            mock_get.return_value = _ok_response(snapshot)
            reading = poller.poll()

        assert reading is not None, f"pressure_hpa={pressure} sollte am Grenzwert akzeptiert werden"
        assert reading.pressure_hpa == pressure
        assert len(fake_repo.readings) == 1


def test_poll_out_of_range_air_temp_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "air_temp_c": 99.0}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "air_temp_c ausserhalb des gueltigen Bereichs: 99.0" in caplog.text


@pytest.mark.parametrize("value", [-50.0, 50.0])
def test_poll_temperature_at_boundaries_saves(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, value: float
) -> None:
    snapshot = {**valid_snapshot, "surface_temp_c": value, "air_temp_c": value}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
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

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.humidity_pct == value
    assert len(fake_repo.readings) == 1
    # Seiteneffekt der Feuchte-Grenze auf den Taupunkt explizit pruefen:
    # Bei RH=0 % ist der Taupunkt nicht bestimmbar -> dew_point_c=None (Fail-safe, NF-01);
    # bei RH=100 % ist er regulaer berechenbar -> ein konkreter Wert.
    if value == 0.0:
        assert reading.dew_point_c is None
    else:
        assert reading.dew_point_c is not None


def test_poll_measured_at_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "measured_at": 1234567890}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "measured_at muss ein String sein" in caplog.text


def test_poll_measured_at_without_timezone_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "measured_at": "2026-06-23T10:00:00"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "measured_at muss Zeitzoneninformation enthalten (UTC)" in caplog.text


def test_poll_sensor_id_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "sensor_id": 123}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "sensor_id muss ein String sein" in caplog.text


def test_poll_non_numeric_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "surface_temp_c": "kalt"}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "surface_temp_c muss eine Zahl sein, erhalten: 'kalt'" in caplog.text


@pytest.mark.parametrize("field", ["surface_temp_c", "air_temp_c", "humidity_pct"])
def test_poll_nan_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, field: str
) -> None:
    snapshot = {**valid_snapshot, field: math.nan}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0


@pytest.mark.parametrize("field", ["surface_temp_c", "air_temp_c", "humidity_pct"])
def test_poll_inf_required_field_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, field: str
) -> None:
    snapshot = {**valid_snapshot, field: math.inf}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0


def test_poll_missing_optional_status_defaults_to_ok(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    snapshot = dict(valid_snapshot)
    del snapshot["status"]

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is not None
    assert reading.status is SensorStatus.OK
    assert len(fake_repo.readings) == 1


def test_poll_status_not_a_string_does_not_save(
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict, caplog
) -> None:
    snapshot = {**valid_snapshot, "status": 123}

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
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

    with patch("src.ingest.poller.httpx.get", return_value=response):
        reading = poller.poll()

    assert reading is None
    assert len(fake_repo.readings) == 0
    assert "G1-Antwort nicht als JSON parsierbar" in caplog.text


def test_poll_repository_error_is_failsafe(caplog) -> None:
    class RaisingRepository(Repository):
        def save(self, reading: Reading) -> int:
            raise RepositoryError("DB nicht erreichbar")

    repo = RaisingRepository()
    poller = Poller(base_url="http://g1.test", repository=repo)
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with patch("src.ingest.poller.httpx.get") as mock_get:
        mock_get.return_value = _ok_response(snapshot)
        reading = poller.poll()

    assert reading is None
    assert "Speichern des Readings fehlgeschlagen" in caplog.text


def test_poll_unexpected_repository_error_is_not_swallowed(caplog) -> None:
    # Nur RepositoryError soll fail-safe abgefangen werden; andere Exceptions
    # muessen hochgereicht werden, um Programmierfehler nicht zu verschleiern.
    class BuggyRepository(Repository):
        def save(self, reading: Reading) -> int:
            raise RuntimeError("unerwarteter Bug")

    poller = Poller(base_url="http://g1.test", repository=BuggyRepository())
    snapshot = {
        "measured_at": "2026-06-23T10:00:00Z",
        "sensor_id": "anr-rwy-01",
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96,
    }

    with pytest.raises(RuntimeError, match="unerwarteter Bug"):
        with patch("src.ingest.poller.httpx.get") as mock_get:
            mock_get.return_value = _ok_response(snapshot)
            poller.poll()


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
    poller: Poller, fake_repo: FakeRepository, valid_snapshot: dict
) -> None:
    # Grenzfall (strict <): ein Taupunkt GENAU auf MIN_PLAUSIBLE_DEW_POINT_C ist noch
    # plausibel und wird behalten (nur Werte echt darunter -> None, s. near_zero-Test).
    with patch("src.ingest.poller.calculate_dew_point", return_value=MIN_PLAUSIBLE_DEW_POINT_C):
        with patch("src.ingest.poller.httpx.get") as mock_get:
            mock_get.return_value = _ok_response(valid_snapshot)
            reading = poller.poll()

    assert reading is not None
    assert reading.dew_point_c == MIN_PLAUSIBLE_DEW_POINT_C
    assert fake_repo.readings[0].dew_point_c == MIN_PLAUSIBLE_DEW_POINT_C
