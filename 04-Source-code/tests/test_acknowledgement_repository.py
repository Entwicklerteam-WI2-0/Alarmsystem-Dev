"""Tests fuer die Quittierungs-Persistenz (DTB-63, NF-09).

Prueft In-Memory- und MySQL-Double: erfolgreiche Quittierung, Double-Ack-Blockade,
Alarm-not-found und DB-Fehler-Handling.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm
from src.storage.acknowledgement_repository import (
    InMemoryAcknowledgementRepository,
    MySqlAcknowledgementRepository,
)
from src.storage.alarm_repository import InMemoryAlarmRepository
from src.storage.repository import RepositoryError

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


def _active_alarm(alarm_id: int = 1) -> Alarm:
    return Alarm(
        id=alarm_id,
        assessment_id=42,
        severity=AlarmSeverity.WARNING,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )


def test_in_memory_acknowledge_updates_state_and_returns_ack():
    alarm_repo = InMemoryAlarmRepository()
    ack_repo = InMemoryAcknowledgementRepository(alarm_repo)
    alarm_repo.save(_active_alarm())

    ack = ack_repo.acknowledge(1, "tower-ops-01", "Gesehen", _T0)

    assert ack.alarm_id == 1
    assert ack.operator == "tower-ops-01"
    assert ack.note == "Gesehen"
    assert ack.ts == _T0
    assert not hasattr(alarm_repo, "acknowledge")  # Repo bleibt save-only
    # Der Alarm im geteilten Speicher ist jetzt acknowledged:
    alarm = next(a for a in alarm_repo._alarms if a.id == 1)
    assert alarm.state is AlarmState.ACKNOWLEDGED


def test_in_memory_acknowledge_unknown_alarm_raises():
    ack_repo = InMemoryAcknowledgementRepository()

    with pytest.raises(ValueError, match="Alarm 99 nicht gefunden"):
        ack_repo.acknowledge(99, "op", None, _T0)


def test_in_memory_double_ack_raises():
    alarm_repo = InMemoryAlarmRepository()
    ack_repo = InMemoryAcknowledgementRepository(alarm_repo)
    alarm_repo.save(_active_alarm())
    ack_repo.acknowledge(1, "op", None, _T0)

    with pytest.raises(ValueError, match="bereits im Zustand 'acknowledged'"):
        ack_repo.acknowledge(1, "op", None, _T0)


def _mock_transaction():
    """Baut (tx, cursor) fuer `with transaction() as conn, conn.cursor() as cur`."""
    cursor = MagicMock()
    cursor.lastrowid = 1
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    tx = MagicMock()
    tx.__enter__.return_value = conn
    return tx, cursor


def test_mysql_acknowledge_happy_path():
    tx, cursor = _mock_transaction()
    cursor.fetchone.return_value = {
        "id": 1,
        "assessment_id": 42,
        "severity": "warning",
        "raised_at": _T0.replace(tzinfo=None),
        "state": "active",
    }
    cursor.lastrowid = 7
    with patch("src.storage.acknowledgement_repository.transaction", return_value=tx):
        ack = MySqlAcknowledgementRepository().acknowledge(1, "op", "note", _T0)

    assert ack.id == 7
    assert ack.alarm_id == 1
    assert ack.operator == "op"


def test_mysql_acknowledge_alarm_not_found():
    tx, cursor = _mock_transaction()
    cursor.fetchone.return_value = None
    with patch("src.storage.acknowledgement_repository.transaction", return_value=tx):
        with pytest.raises(ValueError, match="Alarm 1 nicht gefunden"):
            MySqlAcknowledgementRepository().acknowledge(1, "op", None, _T0)


def test_mysql_acknowledge_already_acknowledged():
    tx, cursor = _mock_transaction()
    cursor.fetchone.return_value = {
        "id": 1,
        "assessment_id": 42,
        "severity": "warning",
        "raised_at": _T0.replace(tzinfo=None),
        "state": "acknowledged",
    }
    with patch("src.storage.acknowledgement_repository.transaction", return_value=tx):
        with pytest.raises(ValueError, match="bereits im Zustand 'acknowledged'"):
            MySqlAcknowledgementRepository().acknowledge(1, "op", None, _T0)


def test_mysql_acknowledge_db_error_becomes_repository_error():
    from src.storage.database import DatabaseConnectionError

    with patch(
        "src.storage.acknowledgement_repository.transaction",
        side_effect=DatabaseConnectionError("DB weg"),
    ):
        with pytest.raises(RepositoryError):
            MySqlAcknowledgementRepository().acknowledge(1, "op", None, _T0)
