"""Integrationstests fuer ReadingRepository gegen eine MariaDB-Test-DB (DTB-28).

Die Tests skippen automatisch, wenn die in .env konfigurierte Test-DB nicht
erreichbar ist. Schema wird idempotent aus migrations/schema.sql aufgebaut.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

import pymysql
import pytest

from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.repository import ReadingRepository, RepositoryError


# ---------------------------------------------------------------------------
# Test-DB Konfiguration
# ---------------------------------------------------------------------------
def _test_db_name() -> str:
    """Ermittelt den Namen der Test-DB.

    Reihenfolge:
        1. DB_NAME_TEST Umgebungsvariable
        2. DB_NAME + "_test"
        3. Fallback "alarmsystem_test"
    """
    if "DB_NAME_TEST" in os.environ:
        return os.environ["DB_NAME_TEST"]
    base = os.environ.get("DB_NAME", "alarmsystem")
    return f"{base}_test"


def _root_connection() -> pymysql.Connection:
    """Verbindung ohne Datenbank-Auswahl, um die Test-DB anzulegen."""
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "alarm"),
        password=os.environ.get("DB_PASSWORD", "changeme"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def db_available() -> bool:
    """Prueft, ob die Test-DB erreichbar ist."""
    try:
        with _root_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
    except pymysql.Error:
        return False
    return True


@pytest.fixture(scope="session")
def test_db_name() -> str:
    return _test_db_name()


@pytest.fixture(scope="session")
def database(test_db_name: str, db_available: bool) -> None:
    """Erstellt die Test-DB und fuehrt migrations/schema.sql aus.

    Skipped die Tests komplett, wenn keine DB-Verbindung moeglich ist.
    """
    if not db_available:
        pytest.skip(
            "MariaDB-Test-DB nicht erreichbar (DB_HOST/DB_PORT/DB_USER/DB_PASSWORD pruefen)"
        )

    with _root_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {test_db_name} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )

    schema_path = Path(__file__).parent.parent / "migrations" / "schema.sql"
    ddl = schema_path.read_text(encoding="utf-8")

    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        database=test_db_name,
        user=os.environ.get("DB_USER", "alarm"),
        password=os.environ.get("DB_PASSWORD", "changeme"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    try:
        with conn.cursor() as cursor:
            for statement in ddl.split(";"):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def db_connection(database: None, test_db_name: str) -> pymysql.Connection:
    """Bietet eine frische Verbindung zur Test-DB und raeumt Tabelle auf."""
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        database=test_db_name,
        user=os.environ.get("DB_USER", "alarm"),
        password=os.environ.get("DB_PASSWORD", "changeme"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute("TRUNCATE TABLE reading")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        yield conn
    finally:
        conn.close()


@pytest.fixture
def repository(db_connection: pymysql.Connection) -> ReadingRepository:
    return ReadingRepository(connection=db_connection)


@pytest.fixture
def sample_reading() -> Reading:
    return Reading(
        sensor_id="anr-rwy-01",
        measured_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
        received_at=datetime(2026, 6, 23, 10, 0, 30, tzinfo=UTC),
        surface_temp_c=-0.4,
        air_temp_c=1.2,
        humidity_pct=96.0,
        pressure_hpa=1013.0,
        dew_point_c=0.63,
        source=Source.REAL,
        status=SensorStatus.OK,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_save_returns_generated_id(repository: ReadingRepository, sample_reading: Reading) -> None:
    reading_id = repository.save(sample_reading)

    assert isinstance(reading_id, int)
    assert reading_id > 0


def test_save_and_get_latest_roundtrip(
    repository: ReadingRepository, sample_reading: Reading
) -> None:
    repository.save(sample_reading)

    latest = repository.get_latest(sensor_id="anr-rwy-01")

    assert len(latest) == 1
    stored = latest[0]
    assert stored.sensor_id == "anr-rwy-01"
    assert stored.surface_temp_c == pytest.approx(-0.4)
    assert stored.air_temp_c == pytest.approx(1.2)
    assert stored.humidity_pct == pytest.approx(96.0)
    assert stored.pressure_hpa == pytest.approx(1013.0)
    assert stored.dew_point_c == pytest.approx(0.63)
    assert stored.source is Source.REAL
    assert stored.status is SensorStatus.OK
    assert stored.measured_at == datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    assert stored.id is not None


def test_get_latest_respects_limit(repository: ReadingRepository) -> None:
    base_time = datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    for i in range(3):
        reading = Reading(
            sensor_id="anr-rwy-02",
            measured_at=base_time.replace(minute=i),
            received_at=base_time.replace(minute=i),
            surface_temp_c=float(i),
            air_temp_c=float(i),
            humidity_pct=50.0,
            source=Source.REAL,
            status=SensorStatus.OK,
        )
        repository.save(reading)

    latest = repository.get_latest(sensor_id="anr-rwy-02", limit=2)

    assert len(latest) == 2
    assert latest[0].surface_temp_c == pytest.approx(2.0)
    assert latest[1].surface_temp_c == pytest.approx(1.0)


def test_get_since_returns_only_matching_readings(repository: ReadingRepository) -> None:
    sensor_id = "anr-rwy-03"
    timestamps = [
        datetime(2026, 6, 23, 9, 55, 0, tzinfo=UTC),
        datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 6, 23, 10, 5, 0, tzinfo=UTC),
    ]
    for ts in timestamps:
        repository.save(
            Reading(
                sensor_id=sensor_id,
                measured_at=ts,
                received_at=ts,
                surface_temp_c=0.0,
                air_temp_c=1.0,
                humidity_pct=80.0,
                source=Source.REAL,
                status=SensorStatus.OK,
            )
        )

    since = datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    result = repository.get_since(sensor_id=sensor_id, since=since)

    assert len(result) == 2
    assert result[0].measured_at == datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    assert result[1].measured_at == datetime(2026, 6, 23, 10, 5, 0, tzinfo=UTC)


def test_get_latest_isolated_per_sensor(repository: ReadingRepository) -> None:
    for sensor_id, temp in [("anr-a", 1.0), ("anr-b", 2.0)]:
        repository.save(
            Reading(
                sensor_id=sensor_id,
                measured_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
                received_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
                surface_temp_c=temp,
                air_temp_c=1.0,
                humidity_pct=80.0,
                source=Source.REAL,
                status=SensorStatus.OK,
            )
        )

    assert repository.get_latest("anr-a")[0].surface_temp_c == pytest.approx(1.0)
    assert repository.get_latest("anr-b")[0].surface_temp_c == pytest.approx(2.0)


def test_save_isolation_between_tests(repository: ReadingRepository) -> None:
    """Sicherstellen, dass das TRUNCATE-Fixture zwischen Tests greift."""
    latest = repository.get_latest(sensor_id="anr-rwy-01")
    assert len(latest) == 0


def test_save_without_connection_raises_repository_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simuliert einen Verbindungsfehler und prueft Fail-safe-Verhalten."""

    def failing_connection() -> pymysql.Connection:
        raise pymysql.Error("Verbindung fehlgeschlagen")

    monkeypatch.setattr("src.storage.repository.get_connection", failing_connection)
    repo = ReadingRepository()
    reading = Reading(
        sensor_id="anr-rwy-01",
        measured_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
        received_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
        surface_temp_c=0.0,
        air_temp_c=1.0,
        humidity_pct=80.0,
        source=Source.REAL,
        status=SensorStatus.OK,
    )

    with pytest.raises(RepositoryError, match="Reading konnte nicht gespeichert werden"):
        repo.save(reading)


def test_save_with_sim_source_roundtrip(repository: ReadingRepository) -> None:
    reading = Reading(
        sensor_id="anr-rwy-sim",
        measured_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
        received_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
        surface_temp_c=-2.0,
        air_temp_c=-1.0,
        humidity_pct=85.0,
        source=Source.SIM,
        status=SensorStatus.FAULT,
    )
    repository.save(reading)

    stored = repository.get_latest("anr-rwy-sim")[0]
    assert stored.source is Source.SIM
    assert stored.status is SensorStatus.FAULT


def test_get_since_empty_for_unknown_sensor(repository: ReadingRepository) -> None:
    since = datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    result = repository.get_since(sensor_id="nicht-existiert", since=since)
    assert result == ()
