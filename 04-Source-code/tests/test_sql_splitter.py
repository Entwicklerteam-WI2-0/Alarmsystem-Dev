"""Unit-Tests fuer tests._sql_splitter (DTB-33/DTB-29).

Der Splitter ist noetig, weil migrations/schema.sql Praeparde-Statements
(PREPARE/EXECUTE/DEALLOCATE) enthaelt, die nicht mehr an jedem Semikolon
getrennt werden duerfen.
"""

from pathlib import Path

from tests._sql_splitter import split_sql_statements


class TestSplitSqlStatements:
    def test_trennt_einfache_statements(self) -> None:
        ddl = "CREATE TABLE a (id INT); CREATE TABLE b (id INT);"
        assert split_sql_statements(ddl) == [
            "CREATE TABLE a (id INT)",
            "CREATE TABLE b (id INT)",
        ]

    def test_ignoriert_semicolon_in_string_literal(self) -> None:
        ddl = "INSERT INTO t VALUES ('a;b'); SELECT 1;"
        assert split_sql_statements(ddl) == [
            "INSERT INTO t VALUES ('a;b')",
            "SELECT 1",
        ]

    def test_ignoriert_semicolon_in_zeilenkommentar(self) -> None:
        ddl = "SELECT 1; -- das ist ein; kommentar\nSELECT 2;"
        assert split_sql_statements(ddl) == [
            "SELECT 1",
            "-- das ist ein; kommentar\nSELECT 2",
        ]

    def test_ignoriert_semicolon_in_mysql_hash_kommentar(self) -> None:
        ddl = "SELECT 1; # das ist ein; kommentar\nSELECT 2;"
        assert split_sql_statements(ddl) == [
            "SELECT 1",
            "# das ist ein; kommentar\nSELECT 2",
        ]

    def test_ignoriert_semicolon_in_blockkommentar(self) -> None:
        ddl = "SELECT 1; /* a; b */ SELECT 2;"
        assert split_sql_statements(ddl) == [
            "SELECT 1",
            "/* a; b */ SELECT 2",
        ]

    def test_leere_statements_werden_herausgefiltert(self) -> None:
        assert split_sql_statements(";;SELECT 1;;") == ["SELECT 1"]

    def test_schema_sql_laesst_sich_aufsplitten(self) -> None:
        schema_path = Path(__file__).parent.parent / "migrations" / "schema.sql"
        ddl = schema_path.read_text(encoding="utf-8")
        statements = split_sql_statements(ddl)

        assert len(statements) >= 5
        assert all(stmt for stmt in statements)
        # Praeparde-Statements fuer bedingte Migrationen sind als einzelne logische
        # Statements erhalten (werden nicht am inneren Semikolon zerrissen).
        prepare_stmts = [s for s in statements if s.upper().startswith("PREPARE")]
        assert len(prepare_stmts) == 3  # 2x Index + 1x Spalte
