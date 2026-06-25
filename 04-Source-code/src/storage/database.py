"""PyMySQL-Verbindungs-Helper (DTB-55 / Backend-Konzept §4).

Zentraler Einstiegspunkt fuer alle rohen PyMySQL-Verbindungen. Repositories nutzen
diese Funktion, statt selbst Verbindungen aufzubauen. Alle Zeitstempel werden als
UTC gespeichert (MySQL DATETIME(3) ist zeitzonenlos).
"""

import os
from collections.abc import Generator
from contextlib import contextmanager

import pymysql


def _env(key: str, default: str) -> str:
    """Liest einen String-Wert aus den Umgebungsvariablen."""
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    """Liest einen Integer-Wert aus den Umgebungsvariablen."""
    return int(os.environ.get(key, str(default)))


def get_connection() -> pymysql.Connection:
    """Baut eine neue PyMySQL-Verbindung aus den Umgebungsvariablen auf.

    Variablen (siehe .env.example):
        DB_HOST, DB_PORT (default 3306), DB_NAME, DB_USER, DB_PASSWORD

    Returns:
        Eine offene pymysql.Connection mit autocommit=False.

    Raises:
        pymysql.Error: Bei Verbindungsfehlern (Repository faengt diese auf).
    """
    return pymysql.connect(
        host=_env("DB_HOST", "localhost"),
        port=_env_int("DB_PORT", 3306),
        database=_env("DB_NAME", "alarmsystem"),
        user=_env("DB_USER", "alarm"),
        password=_env("DB_PASSWORD", "changeme"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


@contextmanager
def connection() -> Generator[pymysql.Connection, None, None]:
    """Kontextmanager fuer eine PyMySQL-Verbindung.

    Schliesst die Verbindung automatisch am Ende des Blocks. Transaktionen
    muessen vom Aufrufer explizit committed werden (Fail-safe, NF-01).
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
