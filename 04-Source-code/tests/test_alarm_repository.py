"""Tests fuer das Alarm-Persistenz-Repository (DTB-27).

DB-freier Kern: InMemory-Double + MySQL-Variante mit gemocktem `transaction`.
Echte MariaDB-Integrationstests (FK-/CHECK-Verletzung, Roundtrip) folgen nach
DTB-21 (geteilte conftest-Fixtures). Muster wie tests/test_audit_repository.py.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pymysql
import pytest

from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm
from src.storage.alarm_repository import (
    AlarmRepository,
    InMemoryAlarmRepository,
    MySqlAlarmRepository,
)
from src.storage.database import DatabaseConfigError, DatabaseConnectionError
from src.storage.repository import RepositoryError

UTC_NOW = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


def _alarm(**overrides) -> Alarm:
    base = dict(
        assessment_id=1,
        severity=AlarmSeverity.WARNING,
        raised_at=UTC_NOW,
    )
    base.update(overrides)
    return Alarm(**base)


def _mock_transaction():
    """Baut (tx, cursor) fuer `with transaction() as conn, conn.cursor() as cur`."""
    cursor = MagicMock()
    cursor.lastrowid = 1
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    tx = MagicMock()
    tx.__enter__.return_value = conn
    return tx, cursor


# --- InMemory-Double (T1) ---


def test_inmemory_save_returns_generated_id():
    repo = InMemoryAlarmRepository()
    assert repo.save(_alarm()) == 1


def test_inmemory_save_increments_id():
    repo = InMemoryAlarmRepository()
    repo.save(_alarm())
    assert repo.save(_alarm()) == 2


def test_inmemory_saved_alarm_is_readable_and_active():
    repo = InMemoryAlarmRepository()
    repo.save(_alarm(severity=AlarmSeverity.CRITICAL))
    gespeichert = repo.all()
    assert len(gespeichert) == 1
    assert gespeichert[0].id == 1
    assert gespeichert[0].severity is AlarmSeverity.CRITICAL
    assert gespeichert[0].state is AlarmState.ACTIVE  # ausgeloeste Alarme sind aktiv (V8)


def test_inmemory_is_an_alarmrepository():
    assert isinstance(InMemoryAlarmRepository(), AlarmRepository)


# --- MySQL-Variante (T2/T3), transaction gemockt ---


def test_mysql_save_uses_parametrized_insert():
    tx, cursor = _mock_transaction()
    with patch("src.storage.alarm_repository.transaction", return_value=tx):
        new_id = MySqlAlarmRepository().save(_alarm(severity=AlarmSeverity.CRITICAL))
    assert new_id == 1
    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args[0]
    assert sql.strip().upper().startswith("INSERT INTO ALARM")
    # parametrisiert: Werte in params, NICHT im SQL-String (SQL-Injection-Schutz, V2)
    assert "%s" in sql
    assert "critical" not in sql
    assert "critical" in params  # severity-Enum als .value uebergeben (V5)


def test_mysql_save_returns_lastrowid():
    tx, cursor = _mock_transaction()
    cursor.lastrowid = 42
    with patch("src.storage.alarm_repository.transaction", return_value=tx):
        assert MySqlAlarmRepository().save(_alarm()) == 42


@pytest.mark.parametrize("startup_error", [DatabaseConnectionError, DatabaseConfigError])
def test_mysql_save_wraps_startup_error_failsafe(startup_error):
    with patch(
        "src.storage.alarm_repository.transaction",
        side_effect=startup_error("Startup-Fehler"),
    ):
        with pytest.raises(RepositoryError):  # V4: nie roher Fehler, Alarm nicht still verloren
            MySqlAlarmRepository().save(_alarm())


def test_mysql_save_wraps_query_error_failsafe():
    # CHECK-/FK-Verletzung kommt als pymysql.Error aus cursor.execute (V9).
    tx, cursor = _mock_transaction()
    cursor.execute.side_effect = pymysql.Error("CHECK/FK verletzt")
    with patch("src.storage.alarm_repository.transaction", return_value=tx):
        with pytest.raises(RepositoryError):
            MySqlAlarmRepository().save(_alarm())


def test_mysql_save_missing_lastrowid_failsafe():
    tx, cursor = _mock_transaction()
    cursor.lastrowid = None
    with patch("src.storage.alarm_repository.transaction", return_value=tx):
        with pytest.raises(RepositoryError):  # V6: kein int(None)
            MySqlAlarmRepository().save(_alarm())


# --- V7 wird am Modell-Rand erzwungen (Alarm-Konstruktion), nicht im Repo ---


def test_naive_raised_at_rejected_at_model_boundary():
    from pydantic import ValidationError

    naive = datetime(2026, 6, 26, 12, 0)  # bewusst ohne tzinfo
    with pytest.raises(ValidationError):
        Alarm(assessment_id=1, severity=AlarmSeverity.WARNING, raised_at=naive)
