"""Tests fuer das append-only Audit-Log-Repository (DTB-29 / NF-09).

Kernverhalten (Tagebuch-Prinzip): Eintraege koennen NUR angehaengt werden.
Es gibt bewusst KEIN Aendern und KEIN Loeschen -- append-only schon per Design
der Schnittstelle (zweite Absicherung folgt auf DB-Ebene via Trigger/Grants).
"""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pymysql
import pytest

from src.model.enums import AuditEventType
from src.model.schemas import AuditLogEntry
from src.storage.audit_repository import (
    AuditRepository,
    InMemoryAuditRepository,
    MySqlAuditRepository,
)
from src.storage.database import DatabaseConfigError, DatabaseConnectionError
from src.storage.repository import RepositoryError

UTC_NOW = datetime(2026, 6, 25, 10, 0, 0, tzinfo=UTC)


def _entry(**overrides) -> AuditLogEntry:
    base = dict(
        ts=UTC_NOW,
        event_type=AuditEventType.ASSESSMENT_MADE,
        entity_type="assessment",
        entity_id=1,
    )
    base.update(overrides)
    return AuditLogEntry(**base)


def test_append_returns_generated_id():
    # Arrange
    repo = InMemoryAuditRepository()
    # Act
    new_id = repo.append(_entry())
    # Assert: das Speichermedium vergibt eine ID (wie AUTO_INCREMENT).
    assert new_id == 1


def test_appended_entries_are_readable_in_order():
    # Arrange
    repo = InMemoryAuditRepository()
    # Act
    repo.append(_entry(event_type=AuditEventType.READING_INGESTED))
    repo.append(_entry(event_type=AuditEventType.ALARM_RAISED))
    # Assert: beide Eintraege bleiben in Reihenfolge erhalten.
    events = [e.event_type for e in repo.all()]
    assert events == [AuditEventType.READING_INGESTED, AuditEventType.ALARM_RAISED]


def test_repository_is_append_only_by_design():
    # Assert: die Schnittstelle bietet KEIN update/delete -- nur anhaengen.
    # So kann ein Tagebuch-Eintrag per Design nicht geaendert/geloescht werden.
    assert not hasattr(AuditRepository, "update")
    assert not hasattr(AuditRepository, "delete")


# --- MySqlAuditRepository (DTB-29 / DTB-55): rohes PyMySQL, nur INSERT ---


def _mock_transaction(lastrowid: int = 1):
    """Baut ein Mock fuer den transaction()-Kontextmanager mit Cursor."""
    cursor = MagicMock()
    cursor.lastrowid = lastrowid
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    # __exit__ darf Exceptions aus dem with-Body NICHT unterdruecken, sonst maskiert
    # der Mock einen pymysql.Error, der real bis zum except-Block durchschlagen muss.
    conn.cursor.return_value.__exit__.return_value = False
    tx = MagicMock()
    tx.__enter__.return_value = conn
    tx.__exit__.return_value = False
    return tx, cursor


def test_mysql_append_uses_parametrized_insert_only():
    # Arrange
    tx, cursor = _mock_transaction(lastrowid=42)
    with patch("src.storage.audit_repository.transaction", return_value=tx):
        repo = MySqlAuditRepository()
        # Act
        new_id = repo.append(_entry())
    # Assert: ID kommt aus der DB (lastrowid).
    assert new_id == 42
    # Assert: genau ein execute, und zwar ein INSERT (kein UPDATE/DELETE).
    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args[0]
    assert sql.strip().upper().startswith("INSERT INTO AUDIT_LOG")
    # Assert: parametrisiert -- Werte stehen in params, NICHT im SQL-String
    # (Schutz vor SQL-Injection; nie String-Formatierung).
    assert "%s" in sql
    assert "assessment_made" not in sql
    assert "assessment_made" in params


def test_mysql_append_serializes_detail_as_json():
    # Arrange
    tx, cursor = _mock_transaction()
    with patch("src.storage.audit_repository.transaction", return_value=tx):
        # Act
        new_id = MySqlAuditRepository().append(_entry(detail={"risk": "orange"}))
    # Assert: Rueckgabewert kommt aus der DB (lastrowid=1 im Mock-Default).
    assert new_id == 1
    # Assert: das JSON-Feld wird als JSON-String uebergeben.
    _, params = cursor.execute.call_args[0]
    assert json.dumps({"risk": "orange"}) in params


@pytest.mark.parametrize("startup_error", [DatabaseConnectionError, DatabaseConfigError])
def test_mysql_append_wraps_startup_error_failsafe(startup_error):
    # Arrange: transaction() schlaegt schon beim Aufbau fehl -- entweder Verbindung
    # (DatabaseConnectionError) ODER Konfiguration (DatabaseConfigError).
    with patch(
        "src.storage.audit_repository.transaction",
        side_effect=startup_error("Startup-Fehler"),
    ):
        # Assert: beide werden als RepositoryError nach oben gereicht
        # (Aufrufer kann fail-safe reagieren), nicht als roher Fehler.
        with pytest.raises(RepositoryError):
            MySqlAuditRepository().append(_entry())


def test_mysql_append_wraps_query_error_failsafe():
    # Arrange: die Query selbst schlaegt fehl (z. B. CHECK-Constraint-Verletzung bei
    # ungueltigem event_type) -> cursor.execute wirft pymysql.Error, NICHT
    # DatabaseConnectionError.
    tx, cursor = _mock_transaction()
    cursor.execute.side_effect = pymysql.Error("CHECK-Constraint verletzt")
    with patch("src.storage.audit_repository.transaction", return_value=tx):
        # Assert: auch Query-/Treiberfehler werden fail-safe zu RepositoryError
        # heruntergebrochen (NF-01), nicht als roher pymysql.Error durchgereicht.
        with pytest.raises(RepositoryError):
            MySqlAuditRepository().append(_entry())


def test_mysql_append_missing_lastrowid_failsafe():
    # Arrange: die DB vergibt keine AUTO_INCREMENT-ID -> lastrowid ist None.
    tx, cursor = _mock_transaction()
    cursor.lastrowid = None
    with patch("src.storage.audit_repository.transaction", return_value=tx):
        # Assert: fehlende ID -> RepositoryError statt TypeError aus int(None).
        with pytest.raises(RepositoryError):
            MySqlAuditRepository().append(_entry())


def test_mysql_append_with_none_detail_passes_none():
    # Arrange: Eintrag ohne detail -> detail_json muss None bleiben (kein String "null").
    tx, cursor = _mock_transaction()
    with patch("src.storage.audit_repository.transaction", return_value=tx):
        # Act
        MySqlAuditRepository().append(_entry(detail=None))
    # Assert: das letzte Param (detail) ist None.
    _, params = cursor.execute.call_args[0]
    assert params[-1] is None
