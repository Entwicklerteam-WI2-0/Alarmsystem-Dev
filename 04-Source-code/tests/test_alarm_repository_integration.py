"""Integrationstests fuer MySqlAlarmRepository gegen eine echte MariaDB-Test-DB (DTB-27 T4).

Skippen automatisch, wenn keine Test-DB erreichbar ist (CI ist DB-frei). Schema idempotent
aus migrations/schema.sql. Muster wie test_storage_repository.py; die geteilte DB-Fixture-
Konsolidierung erfolgt mit DTB-21.
"""

import os
import re
from datetime import UTC, datetime
from pathlib import Path

import pymysql
import pytest

from src.model.enums import AlarmSeverity
from src.model.schemas import Alarm
from src.storage.alarm_repository import MySqlAlarmRepository
from src.storage.database import DatabaseConfig
from src.storage.repository import RepositoryError
from tests._sql_splitter import split_sql_statements

_UTC_NOW = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)

# DDL-Identifier koennen in MySQL NICHT parametrisiert werden; der aus Env-Vars stammende
# DB-Name wird daher vor der Interpolation in CREATE DATABASE auf [A-Za-z0-9_] geweisslistet
# (verhindert DDL-Injection ueber manipulierte Env-Vars im CI-Kontext). fullmatch statt match,
# weil `$` in Python auch vor einem abschliessenden \n matcht (Trailing-Newline aus Env-Dateien).
_DB_NAME_RE = re.compile(r"[A-Za-z0-9_]+")


def _test_db_name() -> str:
    if "DB_NAME_TEST" in os.environ:
        name = os.environ["DB_NAME_TEST"]
    else:
        name = f"{os.environ.get('DB_NAME', 'alarmsystem')}_test"
    if not _DB_NAME_RE.fullmatch(name):
        raise ValueError(f"Ungueltiger Test-DB-Name (nur [A-Za-z0-9_] erlaubt): {name!r}")
    return name


def _conn_params(**extra) -> dict:
    base = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "alarm"),
        "password": os.environ.get("DB_PASSWORD", "changeme"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }
    base.update(extra)
    return base


@pytest.fixture(scope="session")
def db_available() -> bool:
    try:
        conn = pymysql.connect(**_conn_params(autocommit=True))
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
    except pymysql.Error:
        return False
    return True


@pytest.fixture(scope="session")
def database(db_available: bool) -> str:
    if not db_available:
        pytest.skip("MariaDB-Test-DB nicht erreichbar (DB_HOST/DB_PORT/DB_USER/DB_PASSWORD).")
    name = _test_db_name()
    root = pymysql.connect(**_conn_params(autocommit=True))
    with root.cursor() as cursor:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    root.close()
    ddl = (Path(__file__).parent.parent / "migrations" / "schema.sql").read_text(encoding="utf-8")
    conn = pymysql.connect(**_conn_params(database=name, autocommit=False))
    try:
        with conn.cursor() as cursor:
            # Echter Statement-Splitter noetig: schema.sql enthaelt seit den DTB-29/DTB-33-
            # Migrationen Prepared Statements (mehrere ';' pro Block) UND Kommentare mit ';'
            # ("...Tabellen; daher..."). Naives ddl.split(';') zerschnitt mitten im Kommentar
            # -> 1064. split_sql_statements ignoriert ';' in Strings/Kommentaren (Spiegel #119).
            for statement in split_sql_statements(ddl):
                cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return name


@pytest.fixture
def db_config(database: str) -> DatabaseConfig:
    return DatabaseConfig(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        name=database,
        user=os.environ.get("DB_USER", "alarm"),
        password=os.environ.get("DB_PASSWORD", "changeme"),
    )


@pytest.fixture
def assessment_id(database: str) -> int:
    """Raeumt alarm-/audit-/assessment-Tabellen und legt eine Assessment-Zeile fuer den FK an."""
    conn = pymysql.connect(**_conn_params(database=database, autocommit=False))
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


def _alarm(assessment_id: int, **overrides) -> Alarm:
    base = dict(assessment_id=assessment_id, severity=AlarmSeverity.CRITICAL, raised_at=_UTC_NOW)
    base.update(overrides)
    return Alarm(**base)


def test_save_roundtrip(db_config: DatabaseConfig, assessment_id: int):
    repo = MySqlAlarmRepository(db_config)
    alarm_id = repo.save(_alarm(assessment_id))
    assert isinstance(alarm_id, int) and alarm_id > 0

    # Zeile direkt zurueckgelesen (separate Connection -> Commit wirklich erfolgt):
    conn = pymysql.connect(**_conn_params(database=db_config.name, autocommit=True))
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
