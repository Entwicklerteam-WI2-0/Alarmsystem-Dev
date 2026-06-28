"""Tests fuer das append-only `threshold_set`-Repository (DTB-63 / DTB-54).

Kernverhalten: Supersession per neuem Satz (kein update/delete), `get_latest`
liefert den hoechsten `valid_from`, und `append` schreibt Schwellensatz UND
`threshold_changed`-Audit in EINER Transaktion (NF-09-Atomaritaet).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pymysql
import pytest

from src.model.enums import AuditEventType
from src.model.schemas import AuditLogEntry, ThresholdSet
from src.storage.database import DatabaseConnectionError
from src.storage.repository import RepositoryError
from src.storage.threshold_set_repository import (
    InMemoryThresholdSetRepository,
    MySqlThresholdSetRepository,
    ThresholdSetRepository,
)

UTC_NOW = datetime(2026, 6, 28, 10, 0, 0, tzinfo=UTC)


def _set(name: str = "satz", valid_from: datetime = UTC_NOW) -> ThresholdSet:
    return ThresholdSet(
        name=name, params={"vereisung": {"x": 1.0}}, valid_from=valid_from, changed_by="operator"
    )


def _audit() -> AuditLogEntry:
    return AuditLogEntry(
        ts=UTC_NOW,
        event_type=AuditEventType.THRESHOLD_CHANGED,
        entity_type="threshold_set",
        actor="operator",
        detail={"name": "satz"},
    )


# --- InMemory-Double ---


def test_inmemory_get_latest_empty_is_none() -> None:
    assert InMemoryThresholdSetRepository().get_latest() is None


def test_inmemory_append_returns_id_and_links_audit() -> None:
    repo = InMemoryThresholdSetRepository()
    new_id = repo.append(_set(), _audit())
    assert new_id == 1
    # Audit ist mit der Satz-ID verknuepft (entity_id) -> Nachvollziehbarkeit (NF-09).
    assert repo.audit_entries()[0].entity_id == 1
    assert repo.audit_entries()[0].event_type == AuditEventType.THRESHOLD_CHANGED


def test_inmemory_get_latest_returns_highest_valid_from() -> None:
    repo = InMemoryThresholdSetRepository()
    repo.append(_set(name="alt", valid_from=datetime(2026, 6, 1, tzinfo=UTC)), _audit())
    repo.append(_set(name="neu", valid_from=datetime(2026, 6, 27, tzinfo=UTC)), _audit())
    latest = repo.get_latest()
    assert latest is not None
    assert latest.name == "neu"


def test_repository_is_append_only_by_design() -> None:
    # Kein update/delete im Interface -> Supersession per neuem Satz (DTB-54).
    assert not hasattr(ThresholdSetRepository, "update")
    assert not hasattr(ThresholdSetRepository, "delete")


# --- MySql: atomarer INSERT threshold_set + audit_log in EINER Transaktion ---


def _mock_transaction(lastrowid: int | None = 7):
    cursor = MagicMock()
    cursor.lastrowid = lastrowid
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = False
    tx = MagicMock()
    tx.__enter__.return_value = conn
    tx.__exit__.return_value = False
    return tx, cursor


def test_mysql_append_writes_set_and_audit_in_one_tx() -> None:
    tx, cursor = _mock_transaction(lastrowid=7)
    with patch("src.storage.threshold_set_repository.transaction", return_value=tx):
        new_id = MySqlThresholdSetRepository().append(_set(), _audit())
    assert new_id == 7
    # Genau zwei INSERTs (threshold_set + audit_log), beide parametrisiert.
    assert cursor.execute.call_count == 2
    first_sql = cursor.execute.call_args_list[0][0][0]
    second_sql = cursor.execute.call_args_list[1][0][0]
    assert first_sql.strip().upper().startswith("INSERT INTO THRESHOLD_SET")
    assert second_sql.strip().upper().startswith("INSERT INTO AUDIT_LOG")
    assert "%s" in first_sql and "%s" in second_sql
    # Audit wird an die vergebene Satz-ID gebunden (entity_id = lastrowid).
    audit_params = cursor.execute.call_args_list[1][0][1]
    assert 7 in audit_params


def test_mysql_append_missing_lastrowid_failsafe() -> None:
    tx, _cursor = _mock_transaction(lastrowid=None)
    with patch("src.storage.threshold_set_repository.transaction", return_value=tx):
        with pytest.raises(RepositoryError):
            MySqlThresholdSetRepository().append(_set(), _audit())


def test_mysql_append_wraps_query_error_failsafe() -> None:
    tx, cursor = _mock_transaction()
    cursor.execute.side_effect = pymysql.Error("CHECK-Constraint verletzt")
    with patch("src.storage.threshold_set_repository.transaction", return_value=tx):
        with pytest.raises(RepositoryError):
            MySqlThresholdSetRepository().append(_set(), _audit())


def test_mysql_get_latest_wraps_db_error_failsafe() -> None:
    with patch(
        "src.storage.threshold_set_repository.get_connection",
        side_effect=DatabaseConnectionError("DB nicht erreichbar"),
    ):
        with pytest.raises(RepositoryError):
            MySqlThresholdSetRepository().get_latest()


def test_mysql_get_latest_maps_row() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": 3,
        "name": "satz",
        "params": {"vereisung": {"x": 1.0}},
        "valid_from": datetime(2026, 6, 27, tzinfo=UTC),
        "changed_by": "operator",
    }
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = False
    cm = MagicMock()
    cm.__enter__.return_value = conn
    cm.__exit__.return_value = False
    with patch("src.storage.threshold_set_repository.get_connection", return_value=cm):
        result = MySqlThresholdSetRepository().get_latest()
    assert result is not None
    assert result.id == 3
    assert result.name == "satz"
    assert result.valid_from.tzinfo is not None  # UTC nachgezogen
