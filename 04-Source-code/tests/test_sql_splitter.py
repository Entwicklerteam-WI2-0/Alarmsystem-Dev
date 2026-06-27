"""Unit-Tests fuer den SQL-Statement-Splitter (tests/_sql_splitter).

Regressions-Schutz: sichert die Kern-Invarianten, die den Schema-Load-Bug ausgeloest haben
(ein Kommentar mit ';' -> naives split(';') zerschnitt mitten im Kommentar -> SQL-1064) und
die dokumentierte Behandlung von String-Literalen und Kommentaren. Kein DB-Zugriff noetig.
"""

from pathlib import Path

from tests._sql_splitter import split_sql_statements


def test_simple_two_statements():
    assert split_sql_statements("SELECT 1; SELECT 2;") == ["SELECT 1", "SELECT 2"]


def test_trailing_statement_without_semicolon():
    assert split_sql_statements("SELECT 1; SELECT 2") == ["SELECT 1", "SELECT 2"]


def test_empty_statements_are_filtered():
    assert split_sql_statements(";;  ;\n;") == []


def test_semicolon_in_line_comment_does_not_split():
    # Genau der ausloesende Bug: ein ';' im Zeilenkommentar darf NICHT splitten.
    sql = "-- Tabellen; daher Kommentar\nSELECT 1;"
    assert split_sql_statements(sql) == ["-- Tabellen; daher Kommentar\nSELECT 1"]


def test_semicolon_in_hash_comment_does_not_split():
    sql = "# note; still comment\nSELECT 1;"
    assert split_sql_statements(sql) == ["# note; still comment\nSELECT 1"]


def test_semicolon_in_block_comment_does_not_split():
    sql = "/* a; b */ SELECT 1;"
    assert split_sql_statements(sql) == ["/* a; b */ SELECT 1"]


def test_semicolon_in_string_literal_does_not_split():
    sql = "INSERT INTO t VALUES ('a;b'); SELECT 1;"
    assert split_sql_statements(sql) == ["INSERT INTO t VALUES ('a;b')", "SELECT 1"]


def test_escaped_quote_in_string_literal():
    # SQL-Standard-Escape '' innerhalb eines Literals (das ';' bleibt im String).
    sql = "INSERT INTO t VALUES ('it''s; ok'); SELECT 2;"
    assert split_sql_statements(sql) == ["INSERT INTO t VALUES ('it''s; ok')", "SELECT 2"]


def test_real_schema_sql_parses_cleanly():
    # Das echte schema.sql muss fehlerfrei in mehrere ausfuehrbare Statements zerfallen
    # (CREATE TABLEs + bedingte Migrationen). Schuetzt vor Regressionen, wenn das Schema waechst.
    schema_path = Path(__file__).parent.parent / "migrations" / "schema.sql"
    statements = split_sql_statements(schema_path.read_text(encoding="utf-8"))
    creates = [s for s in statements if "CREATE TABLE IF NOT EXISTS" in s.upper()]
    # threshold_set, reading, assessment, alarm, acknowledgement, audit_log
    assert len(creates) >= 6
    # Der Bug erzeugte ein Fragment, das mit Kommentar-Resttext ("daher wird der") begann:
    assert not any(s.lstrip().startswith("daher") for s in statements)
