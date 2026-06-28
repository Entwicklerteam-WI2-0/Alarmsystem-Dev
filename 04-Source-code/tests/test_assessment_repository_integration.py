"""Integrationstests fuer MySqlAssessmentRepository + MySqlAuditRepository gegen eine
echte MariaDB-Test-DB (DB-Finalisierung 2026-06-27).

Schliesst die zuletzt verbliebene Real-DB-Luecke: assessment (Serving-/Sicherheits-Repo,
DTB-64/DTB-43) und audit_log (NF-09-Trail, DTB-29) waren bislang nur mit gemocktem Cursor
getestet. Hier laufen echte INSERT/SELECT-Roundtrips (Spalten-/Typ-/Enum-/DATETIME(3)-Mapping).

Geteilte DB-Helfer + Fixtures (`db_available`/`database` via conftest, `conn_params`/
`db_config_for`) liegen in tests/_db_helpers (DTB-21-Konsolidierung).
"""

import json
from collections.abc import Generator
from datetime import UTC, datetime

import pymysql
import pytest

from src.model.enums import AuditEventType, RiskLevel
from src.model.schemas import Assessment, AuditLogEntry
from src.storage.assessment_repository import MySqlAssessmentRepository
from src.storage.audit_repository import MySqlAuditRepository
from src.storage.database import DatabaseConfig
from tests._db_helpers import conn_params, db_config_for

_UTC_NOW = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)

_TABLES = ("acknowledgement", "alarm", "audit_log", "assessment", "reading", "threshold_set")


@pytest.fixture
def clean_db(database: str) -> str:
    """Leert alle Tabellen vor jedem Test (Isolation); gibt den Test-DB-Namen zurueck."""
    conn = pymysql.connect(**conn_params(database=database, autocommit=False))
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for tabelle in _TABLES:
                cursor.execute(f"TRUNCATE TABLE {tabelle}")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    finally:
        conn.close()
    return database


@pytest.fixture
def db_connection(clean_db: str) -> Generator[pymysql.Connection, None, None]:
    """DictCursor-Verbindung zur Test-DB (fuer MySqlAssessmentRepository, das eine
    Connection erwartet)."""
    conn = pymysql.connect(**conn_params(database=clean_db, autocommit=False))
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def db_config(clean_db: str) -> DatabaseConfig:
    """DatabaseConfig zur Test-DB (fuer MySqlAuditRepository, das eine Config erwartet)."""
    return db_config_for(clean_db)


# --- MySqlAssessmentRepository (DTB-64 / DTB-43): Serving-/Sicherheits-Persistenz ---


def _assessment(**overrides: object) -> Assessment:
    base = dict(
        ts=_UTC_NOW,
        risk_level=RiskLevel.ORANGE,
        driving_factor="dew_point",
        explanation="dT unter Schwelle",
        surface_temp_c=-1.5,
        dew_point_c=-1.0,
        delta_t=-0.5,
        humidity_pct=92.0,
    )
    base.update(overrides)
    return Assessment(**base)


def test_assessment_save_and_get_latest_roundtrip(db_connection: pymysql.Connection) -> None:
    repo = MySqlAssessmentRepository(connection=db_connection)
    new_id = repo.save(_assessment())
    assert isinstance(new_id, int) and new_id > 0

    latest = repo.get_latest()
    assert latest is not None
    assert latest.id == new_id
    assert latest.risk_level is RiskLevel.ORANGE
    assert latest.driving_factor == "dew_point"
    assert latest.explanation == "dT unter Schwelle"
    assert latest.surface_temp_c == -1.5
    assert latest.dew_point_c == -1.0
    assert latest.delta_t == -0.5
    assert latest.humidity_pct == 92.0
    # DATETIME(3) ist zeitzonenlos -> Repo zieht UTC nach: Roundtrip muss tz-aware + gleich sein.
    assert latest.ts == _UTC_NOW
    assert latest.ts.tzinfo is not None


def test_assessment_get_latest_empty_returns_none(db_connection: pymysql.Connection) -> None:
    repo = MySqlAssessmentRepository(connection=db_connection)
    assert repo.get_latest() is None


def test_assessment_get_latest_returns_highest_ts(db_connection: pymysql.Connection) -> None:
    repo = MySqlAssessmentRepository(connection=db_connection)
    repo.save(
        _assessment(ts=datetime(2026, 6, 26, 11, 0, 0, tzinfo=UTC), risk_level=RiskLevel.GREEN)
    )
    newer_id = repo.save(
        _assessment(ts=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC), risk_level=RiskLevel.RED)
    )
    latest = repo.get_latest()
    assert latest is not None
    assert latest.id == newer_id
    assert latest.risk_level is RiskLevel.RED


def test_assessment_unknown_with_nulled_measurements_roundtrip(
    db_connection: pymysql.Connection,
) -> None:
    # Fail-safe-Form (NF-01): risk_level=unknown mit genullten Messwerten muss persistierbar
    # und exakt so wieder lesbar sein (NULL-Spalten -> None).
    repo = MySqlAssessmentRepository(connection=db_connection)
    new_id = repo.save(
        Assessment(ts=_UTC_NOW, risk_level=RiskLevel.UNKNOWN, driving_factor=None, explanation=None)
    )
    latest = repo.get_latest()
    assert latest is not None
    assert latest.id == new_id
    assert latest.risk_level is RiskLevel.UNKNOWN
    assert latest.driving_factor is None
    assert latest.explanation is None
    assert latest.surface_temp_c is None
    assert latest.dew_point_c is None
    assert latest.delta_t is None
    assert latest.humidity_pct is None
    assert latest.driving_factor is None
    assert latest.explanation is None


# --- MySqlAuditRepository (DTB-29): append-only Audit-Trail (NF-09) ---


def _entry(**overrides: object) -> AuditLogEntry:
    base = dict(
        ts=_UTC_NOW,
        event_type=AuditEventType.ASSESSMENT_MADE,
        entity_type="assessment",
        entity_id=42,
        actor="system",
        detail={"risk": "orange", "delta_t": -0.5},
    )
    base.update(overrides)
    return AuditLogEntry(**base)


def test_audit_append_and_readback(db_config: DatabaseConfig) -> None:
    repo = MySqlAuditRepository(db_config)
    new_id = repo.append(_entry())
    assert isinstance(new_id, int) and new_id > 0

    conn = pymysql.connect(**conn_params(database=db_config.name, autocommit=True))
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM audit_log WHERE id = %s", (new_id,))
            row = cursor.fetchone()
    finally:
        conn.close()
    assert row["event_type"] == "assessment_made"
    assert row["entity_type"] == "assessment"
    assert row["entity_id"] == 42
    assert row["actor"] == "system"
    # detail wird als JSON gespeichert -> MariaDB liefert JSON-Text zurueck.
    assert json.loads(row["detail"]) == {"risk": "orange", "delta_t": -0.5}


def test_audit_append_null_detail_roundtrip(db_config: DatabaseConfig) -> None:
    repo = MySqlAuditRepository(db_config)
    new_id = repo.append(_entry(event_type=AuditEventType.SENSOR_FAULT, detail=None))
    conn = pymysql.connect(**conn_params(database=db_config.name, autocommit=True))
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT event_type, detail FROM audit_log WHERE id = %s", (new_id,))
            row = cursor.fetchone()
    finally:
        conn.close()
    assert row["event_type"] == "sensor_fault"
    assert row["detail"] is None
