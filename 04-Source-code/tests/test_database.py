"""Tests fuer den zentralen PyMySQL-Connection-Helper (DTB-28)."""

from unittest.mock import MagicMock, patch

import pymysql

from src.storage.database import get_connection


def test_get_connection_uses_dict_cursor() -> None:
    """get_connection() muss DictCursor konfigurieren, damit _row_to_reading
    via row["column"] auf Spalten zugreifen kann (DTB-93 Review-Befund HIGH).
    """
    mock_conn = MagicMock()

    with patch("src.storage.database.load_database_config_from_env") as mock_load_cfg, \
         patch("pymysql.connect", return_value=mock_conn) as mock_connect:
        mock_load_cfg.return_value = MagicMock(
            host="db.test",
            port=3306,
            name="alarmsystem",
            user="alarm",
            password="secret",
            connect_timeout=5,
            autocommit=False,
            charset="utf8mb4",
        )

        with get_connection() as conn:
            assert conn is mock_conn

    assert mock_connect.called
    _, kwargs = mock_connect.call_args
    assert kwargs["cursorclass"] is pymysql.cursors.DictCursor
