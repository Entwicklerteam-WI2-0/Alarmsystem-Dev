"""Geteilte DB-Test-Helfer + Fixtures fuer die MariaDB-Integrationstests (DTB-21-Konsolidierung).

EINE Quelle fuer Verbindungsparameter (Port/Charset/Creds aus Env), Test-DB-Name,
Erreichbarkeits-Check und Schema-Load -> kein Copy-Paste-Drift mehr zwischen den
*_integration.py-Modulen. Die Fixtures (`db_available`, `database`) werden in `conftest.py`
re-exportiert und sind dadurch in allen Testmodulen verfuegbar.

Hinweis (Splitter-Limit, vgl. `_sql_splitter`): Backtick-quotierte Identifier (`name`) werden
NICHT als Quote-Kontext erkannt. Fuer das aktuelle schema.sql unkritisch (keine ';' in
Identifiern); bei exotischeren Identifiern hier mitbedenken.
"""

import os
import re
from pathlib import Path

import pymysql
import pytest

from src.storage.database import DatabaseConfig
from tests._sql_splitter import split_sql_statements

# DDL-Identifier sind in MySQL nicht parametrisierbar -> Test-DB-Name aus Env vor der
# Interpolation auf [A-Za-z0-9_] weisslisten (DDL-Injection ueber manipulierte Env-Vars
# verhindern). fullmatch statt match, weil `$` in Python auch vor einem abschliessenden \n
# matcht (Trailing-Newline aus Env-Dateien).
DB_NAME_RE = re.compile(r"[A-Za-z0-9_]+")


def test_db_name() -> str:
    """Name der Wegwerf-Test-DB: DB_NAME_TEST oder `<DB_NAME>_test` (Default alarmsystem_test)."""
    if "DB_NAME_TEST" in os.environ:
        name = os.environ["DB_NAME_TEST"]
    else:
        name = f"{os.environ.get('DB_NAME', 'alarmsystem')}_test"
    if not DB_NAME_RE.fullmatch(name):
        raise ValueError(f"Ungueltiger Test-DB-Name (nur [A-Za-z0-9_] erlaubt): {name!r}")
    return name


def conn_params(**extra: object) -> dict[str, object]:
    """PyMySQL-Verbindungsparameter aus den DB_*-Env-Variablen (DictCursor, utf8mb4)."""
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


def db_config_for(name: str) -> DatabaseConfig:
    """DatabaseConfig (App-Verbindungspfad) fuer `name` aus den DB_*-Env-Variablen."""
    return DatabaseConfig(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        name=name,
        user=os.environ.get("DB_USER", "alarm"),
        password=os.environ.get("DB_PASSWORD", "changeme"),
    )


@pytest.fixture(scope="session")
def db_available() -> bool:
    """True, wenn eine MariaDB ueber die DB_*-Env erreichbar ist (sonst skippen die Tests)."""
    try:
        conn = pymysql.connect(**conn_params(autocommit=True))
    except pymysql.Error:
        return False
    # Verbindung steht -> in jedem Fall schliessen, auch wenn das SELECT wirft
    # (sonst Connection-Leak ueber die Session, da diese Fixture session-scoped ist).
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
    except pymysql.Error:
        return False
    finally:
        conn.close()
    return True


@pytest.fixture(scope="session")
def database(db_available: bool) -> str:
    """Erzeugt (idempotent) die Test-DB, spielt das Schema ein, gibt den Namen zurueck.

    Bei Schema-Aenderungen (neue Spalten, geaenderte Enums) reicht CREATE DATABASE IF NOT
    EXISTS nicht, weil die bestehende DB ihr altes Schema behaelt. Setze
    `DB_FORCE_RECREATE=1`, um die Test-DB vor dem Schema-Load zu droppen und neu
    anzulegen (DTB-21-Review MEDIUM).
    """
    if not db_available:
        pytest.skip("MariaDB-Test-DB nicht erreichbar (DB_HOST/DB_PORT/DB_USER/DB_PASSWORD).")
    name = test_db_name()
    # CREATE DATABASE IF NOT EXISTS ist NICHT idempotent auf Spaltenebene: aendert sich schema.sql
    # (neue Spalten/Enums), existiert die Test-DB schon -> das geaenderte Schema wird nicht neu
    # eingespielt und die Suite laeuft still gegen ein veraltetes Schema. DB_FORCE_RECREATE=1 droppt
    # die Test-DB vorab und baut sie frisch auf (PR#129-Review MEDIUM; vgl. docs/dev-db-setup.md).
    force_recreate = os.environ.get("DB_FORCE_RECREATE", "").strip().lower() in {"1", "true", "yes"}
    root = pymysql.connect(**conn_params(autocommit=True))
    # try/finally: wirft CREATE/DROP DATABASE (z. B. fehlende Rechte), wuerde root.close() sonst
    # uebersprungen -> Connection-Leak ueber die session-scoped Fixture (gleiche Bug-Klasse
    # wie der db_available-Leak, DTB-21-Review).
    try:
        with root.cursor() as cursor:
            if force_recreate:
                # name ist via DB_NAME_RE.fullmatch auf [A-Za-z0-9_] weissgelistet (test_db_name) ->
                # DROP-Interpolation genauso sicher wie das CREATE unten.
                cursor.execute(f"DROP DATABASE IF EXISTS {name}")
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {name} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        root.close()
    schema_path = Path(__file__).parent.parent / "migrations" / "schema.sql"
    if not schema_path.is_file():
        pytest.fail(f"schema.sql fuer Test-DB-Setup nicht gefunden: {schema_path}")
    ddl = schema_path.read_text(encoding="utf-8")
    conn = pymysql.connect(**conn_params(database=name, autocommit=False))
    try:
        with conn.cursor() as cursor:
            # Echter Statement-Splitter: schema.sql hat seit DTB-29/DTB-33 Prepared Statements
            # + Kommentare mit ';' (naives split(';') zerschnitt mitten im Kommentar -> 1064).
            for statement in split_sql_statements(ddl):
                cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return name
