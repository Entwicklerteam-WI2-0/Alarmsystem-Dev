"""Unit-Tests fuer den SQL-Statement-Splitter (tests/_sql_splitter).

Regressions-Schutz: sichert die Kern-Invarianten, die den Schema-Load-Bug ausgeloest haben
(ein Kommentar mit ';' -> naives split(';') zerschnitt mitten im Kommentar -> SQL-1064) und
die dokumentierte Behandlung von String-Literalen und Kommentaren. Kein DB-Zugriff noetig.
"""

from pathlib import Path

import pytest

from tests._sql_splitter import split_sql_statements


def test_simple_two_statements() -> None:
    assert split_sql_statements("SELECT 1; SELECT 2;") == ["SELECT 1", "SELECT 2"]


def test_trailing_statement_without_semicolon() -> None:
    assert split_sql_statements("SELECT 1; SELECT 2") == ["SELECT 1", "SELECT 2"]


def test_empty_statements_are_filtered() -> None:
    assert split_sql_statements(";;  ;\n;") == []


def test_semicolon_in_line_comment_does_not_split() -> None:
    # Genau der ausloesende Bug: ein ';' im Zeilenkommentar darf NICHT splitten.
    sql = "-- Tabellen; daher Kommentar\nSELECT 1;"
    assert split_sql_statements(sql) == ["-- Tabellen; daher Kommentar\nSELECT 1"]


def test_semicolon_in_hash_comment_does_not_split() -> None:
    sql = "# note; still comment\nSELECT 1;"
    assert split_sql_statements(sql) == ["# note; still comment\nSELECT 1"]


def test_semicolon_in_block_comment_does_not_split() -> None:
    sql = "/* a; b */ SELECT 1;"
    assert split_sql_statements(sql) == ["/* a; b */ SELECT 1"]


def test_semicolon_in_string_literal_does_not_split() -> None:
    sql = "INSERT INTO t VALUES ('a;b'); SELECT 1;"
    assert split_sql_statements(sql) == ["INSERT INTO t VALUES ('a;b')", "SELECT 1"]


def test_semicolon_in_double_quoted_string_does_not_split() -> None:
    # Splitter behandelt ' und " gleichwertig als String-Quote.
    sql = 'INSERT INTO t VALUES ("a;b"); SELECT 1;'
    assert split_sql_statements(sql) == ['INSERT INTO t VALUES ("a;b")', "SELECT 1"]


def test_escaped_quote_in_string_literal() -> None:
    # SQL-Standard-Escape '' innerhalb eines Literals (das ';' bleibt im String).
    sql = "INSERT INTO t VALUES ('it''s; ok'); SELECT 2;"
    assert split_sql_statements(sql) == ["INSERT INTO t VALUES ('it''s; ok')", "SELECT 2"]


def test_backtick_identifier_with_semicolon_is_known_limit() -> None:
    # Dokumentiertes Limit: Backticks sind KEIN Quote-Kontext -> ein ';' darin splittet
    # (anders als '...'/"..."). Faengt eine spaetere stille Verhaltensaenderung.
    assert split_sql_statements("CREATE TABLE `a;b` (x INT);") == [
        "CREATE TABLE `a",
        "b` (x INT)",
    ]


def test_real_schema_sql_parses_cleanly() -> None:
    # Das echte schema.sql muss fehlerfrei in mehrere ausfuehrbare Statements zerfallen
    # (CREATE TABLEs + bedingte Migrationen). Schuetzt vor Regressionen, wenn das Schema waechst.
    schema_path = Path(__file__).parent.parent / "migrations" / "schema.sql"
    if not schema_path.exists():
        pytest.fail(f"schema.sql nicht gefunden: {schema_path}")
    statements = split_sql_statements(schema_path.read_text(encoding="utf-8"))
    creates = [s for s in statements if "CREATE TABLE IF NOT EXISTS" in s.upper()]
    # threshold_set, reading, assessment, alarm, acknowledgement, audit_log
    assert len(creates) >= 6
    # Der Bug erzeugte ein Fragment, das mit Kommentar-Resttext ("daher wird der") begann:
    assert not any(s.lstrip().startswith("daher") for s in statements)
