"""Append-only Audit-Log-Repository (DTB-29 / NF-09).

Das Audit-Log ist das "Tagebuch" des Systems: jedes relevante Ereignis wird als
Zeile angehaengt und bleibt unveraenderlich. Die Schnittstelle bietet darum
bewusst NUR `append` -- kein update, kein delete (append-only per Design).

Zweite Absicherung folgt auf DB-Ebene (Trigger + eingeschraenkte Grants, Variante C);
die konkrete MySQL-Implementierung (rohes PyMySQL, parametrisierte Queries) kommt mit
DTB-28/DTB-55. Diese Datei haelt die DB-agnostische Naht + ein In-Memory-Double.
"""

import json
from abc import ABC, abstractmethod

import pymysql
from pymysql.cursors import Cursor

from src.model.schemas import AuditLogEntry
from src.storage.database import (
    DatabaseConfig,
    DatabaseConfigError,
    DatabaseConnectionError,
    transaction,
)
from src.storage.repository import RepositoryError

# Spaltenreihenfolge des INSERT -- entspricht migrations/schema.sql (audit_log).
# id ist AUTO_INCREMENT und wird NICHT gesetzt; ts..detail werden parametrisiert.
# Kanonische Form: andere Schreibpfade (z. B. threshold_set_repository, das den
# Audit-Eintrag in DERSELBEN Transaktion schreibt) gehen ueber _write_entry, statt
# dieses SQL zu duplizieren -- so bleibt eine Schemaaenderung an audit_log an EINER Stelle.
_INSERT_SQL = (
    "INSERT INTO audit_log (ts, event_type, entity_type, entity_id, actor, detail) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)


def _serialize_detail(detail: object | None) -> str | None:
    """Serialisiert das JSON-`detail`-Feld fail-safe (NF-01).

    Nicht-serialisierbare Werte (z. B. datetime, set) werden zu einem RepositoryError,
    damit der Audit-Schreibpfad nicht mit einem rohen TypeError crasht; der Aufrufer
    kann fail-safe reagieren. `None` bleibt `None` (kein String "null").
    """
    if detail is None:
        return None
    try:
        return json.dumps(detail)
    except TypeError as exc:
        raise RepositoryError(f"Audit-Detail ist nicht JSON-serialisierbar: {exc}") from exc


class AuditRepository(ABC):
    """Abstrakte append-only Persistenz fuer Audit-Log-Eintraege.

    Bewusst minimal: nur `append`. Es gibt keine Methode zum Aendern oder Loeschen,
    damit das Tagebuch-Prinzip (NF-09) schon durch die Schnittstelle erzwungen wird.
    """

    @abstractmethod
    def append(self, entry: AuditLogEntry) -> int:
        """Haengt einen Eintrag an und gibt die vergebene ID zurueck.

        Args:
            entry: Der unveraenderliche Tagebuch-Eintrag (AuditLogEntry).

        Returns:
            Die vom Speichermedium vergebene ID (z. B. AUTO_INCREMENT).
        """
        ...


class InMemoryAuditRepository(AuditRepository):
    """In-Memory-Double fuer Tests und lokale Laeufe (keine DB noetig).

    Vergibt fortlaufende IDs ab 1 und haelt die Eintraege in Einfuege-Reihenfolge.
    Spiegelt das append-only-Verhalten der spaeteren MySQL-Implementierung.
    """

    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []

    def append(self, entry: AuditLogEntry) -> int:
        new_id = len(self._entries) + 1
        # Eintrag mit vergebener ID ablegen; das Original bleibt unangetastet.
        self._entries.append(entry.model_copy(update={"id": new_id}))
        return new_id

    def all(self) -> list[AuditLogEntry]:
        """Liest alle Eintraege in Einfuege-Reihenfolge (nur lesen).

        Bewusst NUR auf dem In-Memory-Double (Test-/Lokal-Komfort), nicht im
        append-only-Interface AuditRepository: Lesepfade kommen erst mit einem
        echten Read-Use-Case (YAGNI), kein Teil des Append-only-Vertrags.
        """
        return list(self._entries)


class MySqlAuditRepository(AuditRepository):
    """append-only Audit-Log auf MariaDB/MySQL via rohem PyMySQL (DTB-29, E-35).

    Nutzt den zentralen Connection-Helper (database.py, DTB-55). Schreibt
    ausschliesslich per parametrisiertem INSERT (Injection-Schutz, nie
    String-Formatierung); es gibt bewusst keinen UPDATE-/DELETE-Pfad.

    Die zweite append-only-Absicherung liegt auf DB-Ebene (eingeschraenkte
    Grants: kein UPDATE/DELETE-Recht fuer den App-Benutzer, DTB-54).
    """

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        # Optionale Config (sonst aus Env via database.py); erleichtert Tests.
        self._config = config

    @staticmethod
    def _write_entry(cursor: Cursor, entry: AuditLogEntry) -> int | None:
        """Schreibt EINEN Audit-Eintrag ueber den uebergebenen Cursor und gibt die
        vergebene AUTO_INCREMENT-ID zurueck (oder None, falls keine vergeben wurde).

        Bewusst cursor-basiert (kein eigener Verbindungs-/Transaktions-Aufbau): so kann
        ein Aufrufer den Audit-Eintrag in DERSELBEN Transaktion wie eine andere
        Schreiboperation halten (NF-09-Atomaritaet, z. B. threshold_set + threshold_changed).
        Die kanonische INSERT-Form (_INSERT_SQL) lebt nur hier -- keine Duplikat-SQL in
        anderen Modulen. JSON-`detail` wird ueber _serialize_detail fail-safe serialisiert
        (nicht-serialisierbar -> RepositoryError, bevor das execute laeuft).
        """
        cursor.execute(
            _INSERT_SQL,
            (
                entry.ts,
                entry.event_type.value,
                entry.entity_type,
                entry.entity_id,
                entry.actor,
                _serialize_detail(entry.detail),
            ),
        )
        return cursor.lastrowid

    def append(self, entry: AuditLogEntry) -> int:
        try:
            with transaction(self._config) as conn, conn.cursor() as cursor:
                row_id = self._write_entry(cursor, entry)
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            # Verbindungs-, Config- UND Query-Fehler (z. B. CHECK-Constraint-Verletzung
            # bei ungueltigem event_type, Broken-Pipe mitten in der Query) auf die
            # Domaenen-Exception herunterbrechen, damit Aufrufer fail-safe reagieren
            # koennen (NF-01) statt mit rohem Treiberfehler zu crashen.
            raise RepositoryError("Audit-Eintrag konnte nicht gespeichert werden") from exc
        if row_id is None:
            # Kein AUTO_INCREMENT-Wert vergeben -> Eintrag-ID unbekannt. Fail-safe als
            # Domaenenfehler statt TypeError aus int(None).
            raise RepositoryError("Audit-Eintrag wurde ohne vergebene ID gespeichert")
        return int(row_id)
