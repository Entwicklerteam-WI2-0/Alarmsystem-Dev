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
_INSERT_SQL = (
    "INSERT INTO audit_log (ts, event_type, entity_type, entity_id, actor, detail) "
    "VALUES (%s, %s, %s, %s, %s, %s)"
)


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

    def append(self, entry: AuditLogEntry) -> int:
        # JSON-Feld als String serialisieren (MySQL-Spalte detail ist JSON).
        # Nicht-serialisierbare Werte (z. B. datetime, set) werden abgefangen,
        # damit der Audit-Pfad nicht crasht (NF-01 fail-safe).
        if entry.detail is None:
            detail_json = None
        else:
            try:
                detail_json = json.dumps(entry.detail)
            except TypeError as exc:
                raise RepositoryError(f"Audit-Detail ist nicht JSON-serialisierbar: {exc}") from exc
        params = (
            entry.ts,
            entry.event_type.value,
            entry.entity_type,
            entry.entity_id,
            entry.actor,
            detail_json,
        )
        try:
            with transaction(self._config) as conn, conn.cursor() as cursor:
                cursor.execute(_INSERT_SQL, params)
                # AUTO_INCREMENT-ID des gerade eingefuegten Eintrags.
                row_id = cursor.lastrowid
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
