"""Integrationstests fuer ReadingRepository gegen eine MariaDB-Test-DB (DTB-28).

Die Tests skippen automatisch, wenn die in .env konfigurierte Test-DB nicht
erreichbar ist. Schema wird idempotent aus migrations/schema.sql aufgebaut.
"""

import logging
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pymysql
import pytest

from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.repository import (
    InMemoryReadingRepository,
    ReadingRepository,
    RepositoryError,
)


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
        conn = _root_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
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

    root_conn = _root_connection()
    with root_conn.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS {test_db_name} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    root_conn.close()

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
@pytest.mark.parametrize("bad_limit", [0, -1, -100])
def test_get_latest_rejects_non_positive_limit(bad_limit: int) -> None:
    # Keine DB noetig: der Guard greift vor dem Datenbankzugriff.
    repo = ReadingRepository()
    with pytest.raises(ValueError, match="limit muss positiv sein"):
        repo.get_latest("s1", limit=bad_limit)


@pytest.mark.parametrize("bad_limit", [0, -1, -100])
def test_get_since_rejects_non_positive_limit(bad_limit: int) -> None:
    # Keine DB noetig: der Guard greift vor dem Datenbankzugriff.
    repo = ReadingRepository()
    since = datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="limit muss positiv sein"):
        repo.get_since("s1", since=since, limit=bad_limit)


def test_init_rejects_connection_without_dict_cursor() -> None:
    """Injizierte Verbindung ohne DictCursor wird fail-fast abgelehnt (DTB-93 MEDIUM).

    Ohne DictCursor liefert PyMySQL Tupel statt Dicts, _row_to_reading scheitert bei
    jedem Read -> sonst still als RepositoryError maskiert. Der Guard greift im
    Konstruktor, ohne DB.
    """

    class _TupleCursorConnection:
        cursorclass = pymysql.cursors.Cursor

    with pytest.raises(ValueError, match="DictCursor"):
        ReadingRepository(connection=_TupleCursorConnection())


def test_init_accepts_connection_with_dict_cursor() -> None:
    """Verbindung mit DictCursor wird akzeptiert (Guard wirft nicht)."""

    class _DictCursorConnection:
        cursorclass = pymysql.cursors.DictCursor

    ReadingRepository(connection=_DictCursorConnection())


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


def test_get_since_respects_limit_keeps_freshest(repository: ReadingRepository) -> None:
    # Bei LIMIT-Ueberschreitung behaelt get_since die FRISCHESTEN Readings (Minute 1 und 2),
    # nicht die aeltesten — die juengsten sind fuer die Trend-Extrapolation relevant (DTB-33
    # Review MEDIUM). Rueckgabe bleibt aufsteigend nach measured_at.
    sensor_id = "anr-rwy-04"
    for minute in range(3):
        ts = datetime(2026, 6, 23, 10, minute, 0, tzinfo=UTC)
        repository.save(
            Reading(
                sensor_id=sensor_id,
                measured_at=ts,
                received_at=ts,
                surface_temp_c=float(minute),
                air_temp_c=1.0,
                humidity_pct=80.0,
                source=Source.REAL,
                status=SensorStatus.OK,
            )
        )

    since = datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    result = repository.get_since(sensor_id=sensor_id, since=since, limit=2)

    assert len(result) == 2
    assert result[0].surface_temp_c == pytest.approx(1.0)
    assert result[1].surface_temp_c == pytest.approx(2.0)


def test_inmemory_get_since_limit_keeps_freshest() -> None:
    # Das In-Memory-Double spiegelt die DB-Semantik (laeuft ohne DB): bei LIMIT-
    # Ueberschreitung die FRISCHESTEN Readings behalten, aufsteigend zurueckgeben.
    repo = InMemoryReadingRepository()
    for minute in range(4):
        ts = datetime(2026, 6, 23, 10, minute, 0, tzinfo=UTC)
        repo.save(
            Reading(
                sensor_id="anr-rwy-09",
                measured_at=ts,
                received_at=ts,
                surface_temp_c=float(minute),
                air_temp_c=1.0,
                humidity_pct=80.0,
                source=Source.REAL,
                status=SensorStatus.OK,
            )
        )

    since = datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    result = repo.get_since(sensor_id="anr-rwy-09", since=since, limit=2)

    assert [r.surface_temp_c for r in result] == [pytest.approx(2.0), pytest.approx(3.0)]


def test_get_latest_wraps_row_to_reading_value_error_as_repository_error(
    repository: ReadingRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ValueError aus _row_to_reading muss als RepositoryError fail-safe werden."""

    def _failing_row_to_reading(_row: dict) -> Reading:
        raise ValueError("ungueltiger Enum-Wert")

    monkeypatch.setattr(ReadingRepository, "_row_to_reading", staticmethod(_failing_row_to_reading))
    repository.save(
        Reading(
            sensor_id="anr-rwy-05",
            measured_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
            surface_temp_c=0.0,
            air_temp_c=1.0,
            humidity_pct=80.0,
            source=Source.REAL,
            status=SensorStatus.OK,
        )
    )

    with pytest.raises(RepositoryError, match="Reading konnte nicht gelesen werden"):
        repository.get_latest(sensor_id="anr-rwy-05")


def test_get_latest_wraps_key_error_as_repository_error(
    repository: ReadingRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KeyError aus _row_to_reading muss als RepositoryError fail-safe werden."""

    def _failing_row_to_reading(_row: dict) -> Reading:
        raise KeyError("source")

    monkeypatch.setattr(ReadingRepository, "_row_to_reading", staticmethod(_failing_row_to_reading))
    repository.save(
        Reading(
            sensor_id="anr-rwy-key",
            measured_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
            surface_temp_c=0.0,
            air_temp_c=1.0,
            humidity_pct=80.0,
            source=Source.REAL,
            status=SensorStatus.OK,
        )
    )

    with pytest.raises(RepositoryError, match="Reading konnte nicht gelesen werden"):
        repository.get_latest(sensor_id="anr-rwy-key")


def test_get_latest_wraps_type_error_as_repository_error(
    repository: ReadingRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TypeError aus _row_to_reading muss als RepositoryError fail-safe werden."""

    def _failing_row_to_reading(_row: dict) -> Reading:
        raise TypeError("tuple indices must be integers or slices, not str")

    monkeypatch.setattr(ReadingRepository, "_row_to_reading", staticmethod(_failing_row_to_reading))
    repository.save(
        Reading(
            sensor_id="anr-rwy-type",
            measured_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
            received_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
            surface_temp_c=0.0,
            air_temp_c=1.0,
            humidity_pct=80.0,
            source=Source.REAL,
            status=SensorStatus.OK,
        )
    )

    with pytest.raises(RepositoryError, match="Reading konnte nicht gelesen werden"):
        repository.get_latest(sensor_id="anr-rwy-type")


def test_get_since_rejects_naive_datetime(repository: ReadingRepository) -> None:
    """since muss zeitzonenbewusst sein, sonst ValueError (DTB-93 LOW)."""
    naive_since = datetime(2026, 6, 23, 10, 0, 0)

    with pytest.raises(ValueError, match="since muss zeitzonenbewusst sein"):
        repository.get_since(sensor_id="anr-rwy-01", since=naive_since)


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

    @contextmanager
    def failing_connection(config=None):
        raise pymysql.Error("Verbindung fehlgeschlagen")
        yield

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


def test_row_to_reading_makes_naive_datetimes_utc_aware() -> None:
    """PyMySQL liefert naive datetime-Objekte; _row_to_reading muss tzinfo=UTC setzen.

    Regressionstest fuer den DTB-38-Blocker: is_stale() subtrahiert reading.measured_at
    von einem UTC-aware now(). Sind die DB-Zeitstempel naive, entsteht TypeError.
    """
    row = {
        "id": 1,
        "sensor_id": "anr-rwy-01",
        "measured_at": datetime(2026, 6, 23, 10, 0, 0),
        "received_at": datetime(2026, 6, 23, 10, 0, 30),
        "surface_temp_c": -0.4,
        "air_temp_c": 1.2,
        "humidity_pct": 96.0,
        "pressure_hpa": 1013.0,
        "dew_point_c": 0.63,
        "source": "real",
        "status": "ok",
    }

    reading = ReadingRepository._row_to_reading(row)

    assert reading.measured_at.tzinfo is UTC
    assert reading.received_at.tzinfo is UTC
    assert reading.measured_at == datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)
    # Sicherstellen, dass UTC-aware Zeitstempel subtrahiert werden koennen.
    now = datetime(2026, 6, 23, 10, 1, 0, tzinfo=UTC)
    assert (now - reading.measured_at).total_seconds() == 60.0


def test_fetch_wraps_attribute_error_as_repository_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """AttributeError aus _row_to_reading (z. B. str statt datetime -> .tzinfo) -> RepositoryError.

    DB-frei. Sichert, dass auch dieser Schema-Drift-Fall den RepositoryError-Vertrag
    wahrt, statt unkontrolliert nach oben zu propagieren (DTB-93 MEDIUM).
    """

    class _FakeCursor:
        def __enter__(self) -> "_FakeCursor":
            return self

        def __exit__(self, *exc_info: object) -> bool:
            return False

        def execute(self, *args: object) -> None:
            pass

        def fetchall(self) -> list[dict]:
            return [{"measured_at": "2026-06-23 10:00:00"}]

    class _FakeConnection:
        def cursor(self) -> "_FakeCursor":
            return _FakeCursor()

    def _failing_row_to_reading(_row: dict) -> Reading:
        raise AttributeError("'str' object has no attribute 'tzinfo'")

    monkeypatch.setattr(ReadingRepository, "_row_to_reading", staticmethod(_failing_row_to_reading))

    with pytest.raises(RepositoryError, match="Reading konnte nicht gelesen werden"):
        ReadingRepository._fetch(_FakeConnection(), "SELECT 1", ())


def test_insert_logs_when_rollback_fails(caplog: pytest.LogCaptureFixture) -> None:
    """Schlaegt der Rollback nach einem INSERT-Fehler fehl, wird er geloggt (DTB-93 MEDIUM).

    DB-frei. Die urspruengliche Exception muss unveraendert propagieren; der
    Rollback-Fehler darf nicht spurlos verschwinden (analog database.transaction).
    """

    class _FailingConnection:
        def cursor(self) -> object:
            raise pymysql.Error("INSERT fehlgeschlagen")

        def rollback(self) -> None:
            raise pymysql.Error("Rollback fehlgeschlagen")

    with caplog.at_level(logging.ERROR, logger="src.storage.repository"):
        with pytest.raises(pymysql.Error, match="INSERT fehlgeschlagen"):
            ReadingRepository._insert(_FailingConnection(), ())

    assert any("Rollback" in record.getMessage() for record in caplog.records)
