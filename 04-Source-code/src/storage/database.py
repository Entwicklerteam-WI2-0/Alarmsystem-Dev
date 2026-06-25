"""Zentraler PyMySQL-Connection-Helper (DTB-28-Enabler, E-35).

Bietet eine schlanke Factory fuer kurzlebige Datenbankverbindungen. Alle
Zugangsdaten kommen aus Umgebungsvariablen (NF-07); die Schwellenwert-Config
(`config/thresholds.json`, DTB-15) bleibt hierfuer unberuehrt.

Rohes PyMySQL hinter Repository-Pattern — kein SQLAlchemy, kein ORM.
Fehler beim Verbindungsaufbau, beim Schliessen, bei Ping und bei
Transaktionsoperationen werden in eigene Exceptions gewrapped, damit Aufrufer
(Repositorys, API) nicht vom Treiber abhaengen. Operationen auf der geoeffneten
Connection (Queries, Cursor) bleiben Aufgabe des Repository-Layers.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import pymysql
from pymysql import Error as PyMySQLError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Generator

    from pymysql.connections import Connection


class DatabaseConfigError(Exception):
    """Ungueltige oder unvollstaendige Datenbank-Konfiguration."""


class DatabaseConnectionError(Exception):
    """Verbindungsaufbau oder Datenbankoperation ist fehlgeschlagen.

    Kapselt interne pymysql-Fehler und gibt Aufrufern eine treiberunabhaengige
    Exception, die im Repository-Pattern gefangen werden kann (Fail-safe).
    """


@dataclass(frozen=True)
class DatabaseConfig:
    """Vollstaendiger Satz Verbindungsparameter fuer MariaDB/MySQL.

    Keine Defaults fuer Secrets — die muessen explizit aus der Umgebung kommen.
    Technische Defaults sind bewusst gewaehlt:
    - autocommit=False ermoeglicht atomare Transaktionen ueber transaction().
    - connect_timeout=5 verhindert Haengen beim Verbindungsaufbau.
    """

    host: str
    port: int
    name: str
    user: str
    password: str = field(repr=False)
    connect_timeout: int = 5
    autocommit: bool = False
    charset: str = "utf8mb4"

    def __post_init__(self) -> None:
        for field_name in ("host", "name", "user", "password", "charset"):
            value = getattr(self, field_name)
            if value.strip() == "":
                raise DatabaseConfigError(
                    f"{field_name.upper()} darf nicht leer oder nur Whitespace sein"
                )
        if self.connect_timeout <= 0 or self.connect_timeout > 300:
            raise DatabaseConfigError(
                f"DB_CONNECT_TIMEOUT muss zwischen 1 und 300 s sein, "
                f"erhalten: {self.connect_timeout}"
            )
        if not 1 <= self.port <= 65535:
            raise DatabaseConfigError(
                f"DB_PORT muss ein gueltiger TCP-Port (1-65535) sein, erhalten: {self.port}"
            )


def load_database_config_from_env() -> DatabaseConfig:
    """Laedt die DB-Konfiguration ausschliesslich aus Umgebungsvariablen.

    Validiert Pflichtfelder und numerische Werte. Scheitert laut bei
    Fehlkonfiguration — keine stillen Defaults fuer Zugangsdaten.
    """
    required = {
        "DB_HOST": _getenv_or_raise("DB_HOST"),
        "DB_NAME": _getenv_or_raise("DB_NAME"),
        "DB_USER": _getenv_or_raise("DB_USER"),
        "DB_PASSWORD": _getenv_or_raise("DB_PASSWORD"),
    }

    port = _parse_positive_int("DB_PORT", os.environ.get("DB_PORT", "3306"))
    connect_timeout = _parse_positive_int(
        "DB_CONNECT_TIMEOUT", os.environ.get("DB_CONNECT_TIMEOUT", "5")
    )
    autocommit = _parse_bool(os.environ.get("DB_AUTOCOMMIT", "false"))
    charset = os.environ.get("DB_CHARSET", "utf8mb4").strip() or "utf8mb4"

    return DatabaseConfig(
        host=required["DB_HOST"].strip(),
        port=port,
        name=required["DB_NAME"].strip(),
        user=required["DB_USER"].strip(),
        password=required["DB_PASSWORD"],
        connect_timeout=connect_timeout,
        autocommit=autocommit,
        charset=charset,
    )


def _getenv_or_raise(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise DatabaseConfigError(f"Umgebungsvariable fehlt oder ist leer: {name}")
    return value


def _parse_positive_int(var_name: str, raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise DatabaseConfigError(
            f"{var_name} muss eine ganze Zahl sein, erhalten: {raw!r}"
        ) from exc
    if value <= 0:
        raise DatabaseConfigError(f"{var_name} muss > 0 sein, erhalten: {value}")
    return value


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise DatabaseConfigError(
        f"DB_AUTOCOMMIT muss ein boolscher Wert sein "
        f"(true/false/1/0/yes/no/on/off), erhalten: {raw!r}"
    )


@contextmanager
def get_connection(
    config: DatabaseConfig | None = None,
) -> Generator[Connection, None, None]:
    """Kontextmanager fuer eine kurzlebige PyMySQL-Verbindung.

    Args:
        config: Verbindungsparameter. Wenn None, wird aus Env geladen.

    Yields:
        Eine geoeffnete PyMySQL-Connection.

    Die Verbindung wird beim Verlassen des Kontexts in jedem Fall geschlossen,
    auch bei Exceptions (Fail-safe fuer Connection-Leaks).

    Raises:
        DatabaseConfigError: Bei ungueltiger/fehlender Konfiguration.
        DatabaseConnectionError: Wenn der Verbindungsaufbau fehlschlaegt.
    """
    cfg = config if config is not None else load_database_config_from_env()
    try:
        conn = pymysql.connect(
            host=cfg.host,
            port=cfg.port,
            database=cfg.name,
            user=cfg.user,
            password=cfg.password,
            connect_timeout=cfg.connect_timeout,
            autocommit=cfg.autocommit,
            charset=cfg.charset,
        )
    except (PyMySQLError, OSError) as exc:
        # Infrastruktur-Details separat loggen, nicht in der Exception-Message
        # weitergeben, damit sie nicht versehentlich nach oben geleakt werden.
        logger.warning(
            "Verbindung zu %s:%s/%s fehlgeschlagen: %s",
            cfg.host,
            cfg.port,
            cfg.name,
            exc,
        )
        raise DatabaseConnectionError("Verbindung zur Datenbank fehlgeschlagen") from exc

    try:
        yield conn
    finally:
        try:
            conn.close()
        except PyMySQLError as close_exc:
            # Beim Schliessen koennen keine Daten verloren gehen; wir wollen
            # nicht die urspruengliche Exception ueberdecken. Loggen fuer Betrieb.
            logger.warning(
                "DB-Verbindung konnte nicht ordnungsgemaess geschlossen werden: %s",
                close_exc,
            )


@contextmanager
def transaction(
    config: DatabaseConfig | None = None,
) -> Generator[Connection, None, None]:
    """Kontextmanager fuer eine atomare Datenbanktransaktion.

    Erzwingt autocommit=False auf der Verbindung, committet automatisch,
    wenn der Block erfolgreich durchlaeuft, und rollt bei jeder Exception
    zurueck. Schliesst die Verbindung in jedem Fall.

    Args:
        config: Verbindungsparameter. Wenn None, wird aus Env geladen.

    Yields:
        Eine geoeffnete PyMySQL-Connection im Transaktionskontext.

    Raises:
        DatabaseConfigError: Bei ungueltiger/fehlender Konfiguration.
        DatabaseConnectionError: Wenn Verbindungsaufbau, Commit oder Rollback
            fehlschlagen. Die urspruengliche Exception aus dem Transaktionsblock
            wird nur dann weitergegeben, wenn das Rollback erfolgreich war.
    """
    cfg = config if config is not None else load_database_config_from_env()
    # Eine Transaktion erfordert zwingend autocommit=False; wir erzwingen das
    # auf der Verbindung, unabhaengig von der urspruenglichen Config. replace()
    # uebernimmt alle uebrigen Felder automatisch, damit kein Parameter (z. B.
    # charset, DTB-55) beim Kopieren vergessen werden kann.
    tx_cfg = replace(cfg, autocommit=False)

    with get_connection(tx_cfg) as conn:
        commit_error: PyMySQLError | None = None
        try:
            yield conn
            try:
                conn.commit()
            except PyMySQLError as exc:
                logger.error("DB-Commit fehlgeschlagen: %s", exc)
                commit_error = exc
                raise DatabaseConnectionError("Commit fehlgeschlagen") from exc
        except BaseException as exc:
            is_system_signal = isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit))
            try:
                conn.rollback()
            except PyMySQLError as rollback_exc:
                if is_system_signal:
                    # Prozess-Signale duerfen nicht durch DB-Fehler ueberschattet
                    # werden; wir loggen den Rollback-Fehler und reichen das
                    # urspruengliche Signal weiter.
                    logger.error(
                        "Rollback nach %s fehlgeschlagen: %s",
                        type(exc).__name__,
                        rollback_exc,
                    )
                else:
                    logger.error("DB-Rollback fehlgeschlagen: %s", rollback_exc)
                    # Urspruengliche Exception erhalten: wenn ein Commit-Fehler
                    # vorlag, dessen PyMySQLError als __cause__ verwenden,
                    # sonst die gerade aktive Exception.
                    original_exc = commit_error if commit_error is not None else exc
                    raise DatabaseConnectionError(
                        f"Rollback nach Transaktionsfehler fehlgeschlagen: {rollback_exc}"
                    ) from original_exc
            raise


def ping(config: DatabaseConfig | None = None) -> bool:
    """Prueft, ob eine Verbindung zur Datenbank aufgebaut werden kann.

    Gibt True zurueck, wenn `connect` und `conn.ping()` erfolgreich sind.
    Konfigurationsfehler werden NICHT abgefangen, sondern propagiert, damit
    ein kaputtes Setup nicht als "DB nicht erreichbar" maskiert wird.
    """
    try:
        with get_connection(config) as conn:
            try:
                conn.ping()
                return True
            except PyMySQLError as ping_exc:
                logger.warning("DB-Ping fehlgeschlagen: %s", ping_exc)
                return False
    except DatabaseConfigError:
        raise
    except (DatabaseConnectionError, PyMySQLError, OSError) as conn_exc:
        logger.warning("DB-Verbindungspruefung fehlgeschlagen: %s", conn_exc)
        return False
