"""Integrationstests fuer MySqlAlarmRepository gegen eine echte MariaDB-Test-DB (DTB-27 T4).

Skippen automatisch, wenn keine Test-DB erreichbar ist (CI ist DB-frei). Geteilte DB-Helfer
+ Fixtures (`db_available`/`database` via conftest, `conn_params`/`db_config_for`) liegen in
tests/_db_helpers (DTB-21-Konsolidierung).
"""

from datetime import UTC, datetime

import pymysql
import pytest

from src.model.enums import AlarmSeverity
from src.model.schemas import Alarm
from src.storage.alarm_repository import MySqlAlarmRepository
from src.storage.database import DatabaseConfig
from src.storage.repository import RepositoryError
from tests._db_helpers import conn_params, db_config_for

_UTC_NOW = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def db_config(database: str) -> DatabaseConfig:
    return db_config_for(database)


@pytest.fixture
def assessment_id(database: str) -> int:
    """Raeumt alarm-/audit-/assessment-Tabellen und legt eine Assessment-Zeile fuer den FK an."""
    conn = pymysql.connect(**conn_params(database=database, autocommit=False))
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for tabelle in ("acknowledgement", "alarm", "audit_log", "assessment"):
                cursor.execute(f"TRUNCATE TABLE {tabelle}")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            cursor.execute(
                "INSERT INTO assessment (ts, risk_level) VALUES (%s, %s)", (_UTC_NOW, "orange")
            )
            neue_id = cursor.lastrowid
        conn.commit()  # committen, damit das Repo (eigene Connection) den FK sieht
        return neue_id
    finally:
        conn.close()


def _alarm(assessment_id: int, **overrides: object) -> Alarm:
    base = dict(assessment_id=assessment_id, severity=AlarmSeverity.CRITICAL, raised_at=_UTC_NOW)
    base.update(overrides)
    return Alarm(**base)


def test_save_roundtrip(db_config: DatabaseConfig, assessment_id: int):
    repo = MySqlAlarmRepository(db_config)
    alarm_id = repo.save(_alarm(assessment_id))
    assert isinstance(alarm_id, int) and alarm_id > 0

    # Zeile direkt zurueckgelesen (separate Connection -> Commit wirklich erfolgt):
    conn = pymysql.connect(**conn_params(database=db_config.name, autocommit=True))
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM alarm WHERE id = %s", (alarm_id,))
            row = cursor.fetchone()
    finally:
        conn.close()
    assert row["assessment_id"] == assessment_id
    assert row["severity"] == "critical"
    assert row["state"] == "active"


def test_fk_violation_failsafe(db_config: DatabaseConfig, assessment_id: int):
    # Nicht existierende assessment_id -> FK-Verletzung -> fail-safe RepositoryError.
    repo = MySqlAlarmRepository(db_config)
    with pytest.raises(RepositoryError):
        repo.save(_alarm(assessment_id + 999_999))
