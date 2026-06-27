"""Minimaler SQL-Statement-Splitter fuer migrations/schema.sql.

Beruecksichtigt einfache SQL-String-Literale (', ") sowie Zeilenkommentare
(-- und MySQL-spezifisch #) und Blockkommentare (/* */).
DELIMITER-Aenderungen werden NICHT unterstuetzt.

Notwendig, seit schema.sql Praeparde-Statements (PREPARE/EXECUTE/DEALLOCATE) enthaelt,
die mehrere Semikolons pro logischem Statement haben (MySQL-kompatible bedingte
Migrationen, DTB-29/DTB-33).
"""


def split_sql_statements(ddl: str) -> list[str]:
    """Teilt ein SQL-Skript an Semikolons in ausfuehrbare Statements auf.

    Semikolons innerhalb von String-Literalen und Kommentaren werden ignoriert.
    Leere Statements (z. B. zwischen zwei Semikolons) werden herausgefiltert.
    """
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    string_char = ""
    in_line_comment = False
    in_block_comment = False

    i = 0
    while i < len(ddl):
        char = ddl[i]
        next_char = ddl[i + 1] if i + 1 < len(ddl) else ""

        if in_line_comment:
            current.append(char)
            if char == "\n":
                in_line_comment = False
        elif in_block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                in_block_comment = False
                current.append(next_char)
                i += 1
        elif in_string:
            current.append(char)
            if char == "\\" and next_char:
                current.append(next_char)
                i += 1
            elif char == string_char and next_char == string_char:
                # SQL-Standard-Quote-Escape (z. B. 'it''s ok'); das naechste Zeichen
                # gehoert noch zum Literal und darf keinen String-Abschluss bedeuten.
                current.append(next_char)
                i += 1
            elif char == string_char:
                in_string = False
        else:
            if char == "-" and next_char == "-":
                in_line_comment = True
                current.append(char)
                current.append(next_char)
                i += 1
            elif char == "/" and next_char == "*":
                in_block_comment = True
                current.append(char)
                current.append(next_char)
                i += 1
            elif char == "#":
                in_line_comment = True
                current.append(char)
            elif char in ("'", '"'):
                in_string = True
                string_char = char
                current.append(char)
            elif char == ";":
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            else:
                current.append(char)
        i += 1

    # Restliches Statement ohne abschliessendes Semikolon
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements
