"""Tests fuer den zentralen PyMySQL-Connection-Helper (DTB-28-Enabler, E-35).

Isolierte Unit-Tests mocken `pymysql.connect`; ein optionaler Integrationstest
prueft eine echte MariaDB, falls `DB_HOST` erreichbar ist.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pymysql
import pytest

from src.storage.database import (
    DatabaseConfig,
    DatabaseConfigError,
    DatabaseConnectionError,
    get_connection,
    load_database_config_from_env,
    ping,
    transaction,
)

_CREDENTIAL_PLACEHOLDER = "changeme"


@pytest.fixture
def minimal_env(monkeypatch) -> None:
    """Minimaler gueltiger Satz DB-Env-Variablen (ohne optionale Defaults)."""
    monkeypatch.setenv("DB_HOST", "db.test")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_NAME", "alarmsystem")
    monkeypatch.setenv("DB_USER", "alarm")
    monkeypatch.setenv("DB_PASSWORD", _CREDENTIAL_PLACEHOLDER)
    monkeypatch.delenv("DB_CONNECT_TIMEOUT", raising=False)
    monkeypatch.delenv("DB_AUTOCOMMIT", raising=False)
    monkeypatch.delenv("DB_CHARSET", raising=False)


def _valid_config(autocommit: bool = False) -> DatabaseConfig:
    return DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=autocommit,
    )


def test_database_config_password_is_not_leaked_in_repr() -> None:
    config = _valid_config()
    representation = repr(config)
    assert config.password not in representation


def test_database_config_rejects_empty_or_whitespace_host() -> None:
    with pytest.raises(DatabaseConfigError, match="HOST"):
        DatabaseConfig(
            host="   ",
            port=3306,
            name="alarmsystem",
            user="alarm",
            password=_CREDENTIAL_PLACEHOLDER,
        )


def test_database_config_rejects_empty_password() -> None:
    with pytest.raises(DatabaseConfigError, match="PASSWORD"):
        DatabaseConfig(
            host="db.test",
            port=3306,
            name="alarmsystem",
            user="alarm",
            password="",
        )


def test_database_config_rejects_empty_charset() -> None:
    with pytest.raises(DatabaseConfigError, match="CHARSET"):
        DatabaseConfig(
            host="db.test",
            port=3306,
            name="alarmsystem",
            user="alarm",
            password=_CREDENTIAL_PLACEHOLDER,
            charset="   ",
        )


def test_database_config_validates_port_in_constructor() -> None:
    with pytest.raises(DatabaseConfigError, match="DB_PORT"):
        DatabaseConfig(
            host="db.test",
            port=70000,
            name="alarmsystem",
            user="alarm",
            password=_CREDENTIAL_PLACEHOLDER,
        )


def test_database_config_validates_connect_timeout_in_constructor() -> None:
    with pytest.raises(DatabaseConfigError, match="DB_CONNECT_TIMEOUT"):
        DatabaseConfig(
            host="db.test",
            port=3306,
            name="alarmsystem",
            user="alarm",
            password=_CREDENTIAL_PLACEHOLDER,
            connect_timeout=-1,
        )


def test_database_config_rejects_connect_timeout_above_limit(minimal_env, monkeypatch) -> None:
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "301")

    with pytest.raises(DatabaseConfigError, match="DB_CONNECT_TIMEOUT"):
        load_database_config_from_env()


def test_load_database_config_from_env_parses_all_fields(minimal_env, monkeypatch) -> None:
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "7")
    monkeypatch.setenv("DB_AUTOCOMMIT", "false")

    config = load_database_config_from_env()

    assert config == DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=7,
        autocommit=False,
    )


def test_load_database_config_uses_safe_defaults(minimal_env) -> None:
    config = load_database_config_from_env()

    assert config.connect_timeout == 5
    # Fail-safe: Transaktionskontrolle per Default erwuenscht (E-35, Repository-Pattern).
    assert config.autocommit is False


def test_load_database_config_rejects_missing_required_variable(minimal_env, monkeypatch) -> None:
    monkeypatch.delenv("DB_PASSWORD")

    with pytest.raises(DatabaseConfigError, match="DB_PASSWORD"):
        load_database_config_from_env()


def test_load_database_config_rejects_whitespace_only_value(minimal_env, monkeypatch) -> None:
    monkeypatch.setenv("DB_PASSWORD", "   ")

    with pytest.raises(DatabaseConfigError, match="DB_PASSWORD"):
        load_database_config_from_env()


def test_load_database_config_rejects_invalid_port(minimal_env, monkeypatch) -> None:
    monkeypatch.setenv("DB_PORT", "not-a-number")

    with pytest.raises(DatabaseConfigError, match="DB_PORT"):
        load_database_config_from_env()


def test_load_database_config_rejects_out_of_range_port(minimal_env, monkeypatch) -> None:
    monkeypatch.setenv("DB_PORT", "70000")

    with pytest.raises(DatabaseConfigError, match="DB_PORT"):
        load_database_config_from_env()


def test_load_database_config_rejects_invalid_connect_timeout(minimal_env, monkeypatch) -> None:
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "0")

    with pytest.raises(DatabaseConfigError, match="DB_CONNECT_TIMEOUT"):
        load_database_config_from_env()


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("FALSE", False),
        ("no", False),
        ("off", False),
    ],
)
def test_load_database_config_parses_autocommit_values(
    minimal_env, monkeypatch, raw_value: str, expected: bool
) -> None:
    monkeypatch.setenv("DB_AUTOCOMMIT", raw_value)

    config = load_database_config_from_env()
    assert config.autocommit is expected


def test_load_database_config_rejects_invalid_autocommit(minimal_env, monkeypatch) -> None:
    monkeypatch.setenv("DB_AUTOCOMMIT", "treu")

    with pytest.raises(DatabaseConfigError, match="DB_AUTOCOMMIT"):
        load_database_config_from_env()


def test_get_connection_yields_open_connection_and_closes_it() -> None:
    mock_conn = MagicMock()

    config = DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=False,
    )

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn) as mock_connect:
        with get_connection(config) as conn:
            assert conn is mock_conn

    mock_connect.assert_called_once_with(
        host="db.test",
        port=3306,
        database="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=False,
        charset="utf8mb4",
    )
    mock_conn.close.assert_called_once()


def test_get_connection_passes_connect_timeout_and_autocommit() -> None:
    config = DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=10,
        autocommit=True,
    )

    mock_conn = MagicMock()
    with patch("src.storage.database.pymysql.connect", return_value=mock_conn) as mock_connect:
        with get_connection(config) as conn:
            assert conn is mock_conn

    mock_connect.assert_called_once_with(
        host="db.test",
        port=3306,
        database="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=10,
        autocommit=True,
        charset="utf8mb4",
    )


def test_get_connection_closes_on_exception() -> None:
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = RuntimeError("boom")

    config = DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=False,
    )

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with pytest.raises(RuntimeError, match="boom"):
            with get_connection(config) as conn:
                conn.cursor()

    mock_conn.close.assert_called_once()


def test_get_connection_closes_even_if_close_raises() -> None:
    mock_conn = MagicMock()
    mock_conn.close.side_effect = pymysql.Error("close failed")

    config = DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=False,
    )

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with get_connection(config) as conn:
            assert conn is mock_conn

    mock_conn.close.assert_called_once()


def test_get_connection_wraps_pymysql_error() -> None:
    config = DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=False,
    )

    with patch(
        "src.storage.database.pymysql.connect",
        side_effect=pymysql.Error("Connection refused"),
    ):
        with pytest.raises(DatabaseConnectionError, match="Verbindung zur Datenbank"):
            with get_connection(config) as conn:
                conn.cursor()


def test_get_connection_wraps_os_error() -> None:
    config = DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=False,
    )

    with patch(
        "src.storage.database.pymysql.connect",
        side_effect=OSError("network unreachable"),
    ):
        with pytest.raises(DatabaseConnectionError, match="Verbindung zur Datenbank"):
            with get_connection(config):
                pass


def test_transaction_commits_on_success() -> None:
    mock_conn = MagicMock()

    config = DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=False,
    )

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with transaction(config) as conn:
            assert conn is mock_conn
            conn.cursor().execute("INSERT INTO reading VALUES (1)")

    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_not_called()
    mock_conn.close.assert_called_once()


def test_transaction_rolls_back_on_exception() -> None:
    mock_conn = MagicMock()

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with pytest.raises(RuntimeError, match="boom"):
            with transaction(_valid_config()):
                raise RuntimeError("boom")

    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()


def test_transaction_forces_autocommit_off() -> None:
    """transaction() muss autocommit=False erzwingen, unabhaengig von Config."""
    mock_conn = MagicMock()

    config = _valid_config(autocommit=True)

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn) as mock_connect:
        with transaction(config):
            pass

    mock_connect.assert_called_once()
    assert mock_connect.call_args.kwargs["autocommit"] is False
    mock_conn.commit.assert_called_once()


def test_transaction_propagates_non_default_charset() -> None:
    """transaction() muss einen abweichenden charset durchreichen (DTB-55).

    Regressionstest: tx_cfg entsteht via dataclasses.replace. Faellt charset
    beim Kopieren weg, landet still der Default utf8mb4 auf der Verbindung,
    obwohl die uebergebene Config einen anderen Zeichensatz vorgibt.
    """
    mock_conn = MagicMock()

    config = DatabaseConfig(
        host="db.test",
        port=3306,
        name="alarmsystem",
        user="alarm",
        password=_CREDENTIAL_PLACEHOLDER,
        connect_timeout=5,
        autocommit=False,
        charset="latin1",
    )

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn) as mock_connect:
        with transaction(config):
            pass

    assert mock_connect.call_args.kwargs["charset"] == "latin1"


def test_transaction_wraps_commit_error() -> None:
    mock_conn = MagicMock()
    mock_conn.commit.side_effect = pymysql.Error("constraint violation")

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with pytest.raises(DatabaseConnectionError, match="Commit fehlgeschlagen"):
            with transaction(_valid_config()):
                pass

    # Bei Commit-Fehler wird zur Sicherheit ein Rollback versucht.
    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()


def test_transaction_preserves_original_error_when_commit_and_rollback_fail() -> None:
    """Wenn commit() und rollback() beide fehlschlagen, bleibt der urspruengliche
    Commit-Fehler als __cause__ erhalten, damit das Debugging nicht erschwert wird.
    """
    original_exc = pymysql.Error("constraint violation")
    rollback_exc = pymysql.Error("connection lost")

    mock_conn = MagicMock()
    mock_conn.commit.side_effect = original_exc
    mock_conn.rollback.side_effect = rollback_exc

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with pytest.raises(DatabaseConnectionError) as exc_info:
            with transaction(_valid_config()):
                pass

    raised = exc_info.value
    assert "Rollback nach Transaktionsfehler fehlgeschlagen" in str(raised)
    assert raised.__cause__ is original_exc
    mock_conn.commit.assert_called_once()
    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()


def test_transaction_wraps_rollback_error() -> None:
    mock_conn = MagicMock()
    mock_conn.rollback.side_effect = pymysql.Error("connection lost")

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with pytest.raises(DatabaseConnectionError, match="Rollback nach Transaktionsfehler"):
            with transaction(_valid_config()):
                raise RuntimeError("boom")

    mock_conn.commit.assert_not_called()
    mock_conn.close.assert_called_once()


def test_transaction_rolls_back_on_keyboard_interrupt() -> None:
    mock_conn = MagicMock()

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with pytest.raises(KeyboardInterrupt):
            with transaction(_valid_config()):
                raise KeyboardInterrupt

    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()


def test_transaction_preserves_keyboard_interrupt_despite_rollback_failure(
    caplog,
) -> None:
    """System-Signale duerfen nicht durch DB-Fehler ueberschattet werden."""
    mock_conn = MagicMock()
    mock_conn.rollback.side_effect = pymysql.Error("connection lost")

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with pytest.raises(KeyboardInterrupt):
            with transaction(_valid_config()):
                raise KeyboardInterrupt

    mock_conn.rollback.assert_called_once()
    mock_conn.close.assert_called_once()
    assert "Rollback nach KeyboardInterrupt" in caplog.text


def test_load_database_config_strips_whitespace_from_host_name_user(
    minimal_env, monkeypatch
) -> None:
    monkeypatch.setenv("DB_HOST", "  db.test  ")
    monkeypatch.setenv("DB_NAME", "  alarmsystem  ")
    monkeypatch.setenv("DB_USER", "  alarm  ")

    config = load_database_config_from_env()

    assert config.host == "db.test"
    assert config.name == "alarmsystem"
    assert config.user == "alarm"


def test_ping_returns_true_on_healthy_connection() -> None:
    mock_conn = MagicMock()

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        assert ping(_valid_config()) is True

    mock_conn.ping.assert_called_once()
    mock_conn.close.assert_called_once()


def test_ping_returns_false_when_ping_fails() -> None:
    mock_conn = MagicMock()
    mock_conn.ping.side_effect = pymysql.Error("connection reset")

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        assert ping(_valid_config()) is False

    mock_conn.ping.assert_called_once()
    mock_conn.close.assert_called_once()


def test_ping_returns_false_on_unreachable_database() -> None:
    with patch(
        "src.storage.database.pymysql.connect",
        side_effect=pymysql.Error("Connection refused"),
    ):
        assert ping(_valid_config()) is False


def test_ping_returns_false_on_non_pymysql_error() -> None:
    with patch(
        "src.storage.database.pymysql.connect",
        side_effect=OSError("network unreachable"),
    ):
        assert ping(_valid_config()) is False


def test_ping_propagates_unexpected_error() -> None:
    """Programmierfehler sollen nicht als 'DB nicht erreichbar' maskiert werden."""
    mock_conn = MagicMock()
    mock_conn.ping.side_effect = ValueError("totally unexpected")

    with patch("src.storage.database.pymysql.connect", return_value=mock_conn):
        with pytest.raises(ValueError, match="totally unexpected"):
            ping(_valid_config())


def test_ping_propagates_config_error(minimal_env, monkeypatch) -> None:
    """Konfigurationsfehler duerfen nicht als 'DB nicht erreichbar' maskiert werden."""
    monkeypatch.delenv("DB_PASSWORD")

    with pytest.raises(DatabaseConfigError):
        ping()


@pytest.mark.skipif(
    os.environ.get("DB_HOST") in (None, ""),
    reason="Integrationstest braucht eine erreichbare MariaDB (DB_HOST).",
)
def test_integration_load_config_and_ping_from_env() -> None:
    """Raucht nur, wenn eine echte DB ueber die aktuellen Env-Variablen erreichbar ist."""
    config = load_database_config_from_env()
    assert ping(config) is True
