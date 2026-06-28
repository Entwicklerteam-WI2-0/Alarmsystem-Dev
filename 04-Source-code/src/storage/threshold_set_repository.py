"""Persistenz fuer versionierte Schwellensaetze (`threshold_set`) — DTB-63 / DTB-54.

Append-only Config-Historie: ein neuer Schwellensatz wird per INSERT mit neuem
`valid_from` angelegt (Supersession), NIE per UPDATE/DELETE. Begruendung (E-39 /
DTB-54): `assessment.fk_assessment_threshold` (ohne ON DELETE) verweist auf
historische Saetze; Ueberschreiben/Loeschen wuerde die Nachvollziehbarkeit einer
alten Bewertung brechen. Die DB-Grants vergeben fuer `threshold_set` darum bewusst
nur INSERT/SELECT (grants.sql) — zweite Absicherung unterhalb dieser Schicht.

`append` schreibt den Schwellensatz UND den `threshold_changed`-Audit-Eintrag
(NF-09) in EINER Transaktion: eine Aenderung der Sicherheits-Kalibrierung ohne
ihren Audit-Eintrag waere eine Luecke in der Nachvollziehbarkeit (K6). Beides
committet gemeinsam oder gar nicht.

Die aktive Config liest `src.main.build_runtime` beim Start ueber `get_latest`
(JSON-Datei nur noch als Seed/Fallback). Aenderungen greifen auf das laufende
System beim naechsten kontrollierten Reload/Neustart (Wirksamkeits-Entscheidung
DTB-63) — kein Live-Swap des Runtime-Graphen.

Rohes PyMySQL, ausschliesslich parametrisierte Queries (E-35).
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC
from typing import Any

import pymysql

from src.model.schemas import AuditLogEntry, ThresholdSet
from src.storage.audit_repository import MySqlAuditRepository
from src.storage.database import (
    DatabaseConfig,
    DatabaseConfigError,
    DatabaseConnectionError,
    get_connection,
    transaction,
)
from src.storage.repository import RepositoryError

logger = logging.getLogger(__name__)


class ThresholdSetRepository(ABC):
    """Abstrakte append-only Persistenz fuer versionierte Schwellensaetze.

    Bewusst nur `get_latest` + `append` — kein update/delete (Supersession per
    neuem Satz, DTB-54). `append` ist atomar mit dem Audit-Eintrag (NF-09).
    """

    @abstractmethod
    def get_latest(self) -> ThresholdSet | None:
        """Liefert den zuletzt gueltigen Satz (hoechstes `valid_from`), sonst None.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
        """
        ...

    @abstractmethod
    def append(self, threshold_set: ThresholdSet, audit_entry: AuditLogEntry) -> int:
        """Legt einen neuen Schwellensatz an und schreibt den Audit-Eintrag (atomar).

        Der `audit_entry` wird mit der vergebenen Satz-ID als `entity_id` verknuepft.

        Returns:
            Die vom Speichermedium vergebene Satz-ID (AUTO_INCREMENT).

        Raises:
            RepositoryError: Bei Datenbankfehlern (Aufrufer reagiert fail-safe).
        """
        ...


class InMemoryThresholdSetRepository(ThresholdSetRepository):
    """In-Memory-Double fuer Tests/lokale Laeufe (keine DB noetig).

    Spiegelt das append-only-Verhalten: vergibt fortlaufende IDs ab 1, verknuepft
    den Audit-Eintrag mit der Satz-ID und legt Kopien MIT id ab (kein Aliasing).
    """

    def __init__(self) -> None:
        self._sets: list[ThresholdSet] = []
        self._audit: list[AuditLogEntry] = []

    def get_latest(self) -> ThresholdSet | None:
        if not self._sets:
            return None
        # Hoechstes valid_from gewinnt; bei Gleichstand der spaeter eingefuegte (groessere id).
        return max(self._sets, key=lambda s: (s.valid_from, s.id or 0))

    def append(self, threshold_set: ThresholdSet, audit_entry: AuditLogEntry) -> int:
        new_id = len(self._sets) + 1
        self._sets.append(threshold_set.model_copy(update={"id": new_id}))
        self._audit.append(audit_entry.model_copy(update={"entity_id": new_id}))
        return new_id

    def all(self) -> list[ThresholdSet]:
        """Alle Saetze in Einfuege-Reihenfolge (nur Test-/Lokal-Komfort)."""
        return list(self._sets)

    def audit_entries(self) -> list[AuditLogEntry]:
        """Die mitgeschriebenen Audit-Eintraege (nur Test-/Lokal-Komfort)."""
        return list(self._audit)


class MySqlThresholdSetRepository(ThresholdSetRepository):
    """PyMySQL-Implementierung (E-35). INSERT/SELECT only (DTB-54).

    Args:
        config: Optionale DB-Config (sonst aus Env via database.py); erleichtert Tests.
    """

    _INSERT_SQL = (
        "INSERT INTO threshold_set (name, params, valid_from, changed_by) VALUES (%s, %s, %s, %s)"
    )
    _LATEST_SQL = (
        "SELECT id, name, params, valid_from, changed_by "
        "FROM threshold_set ORDER BY valid_from DESC, id DESC LIMIT 1"
    )

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self._config = config

    def get_latest(self) -> ThresholdSet | None:
        try:
            with get_connection(self._config) as conn, conn.cursor() as cursor:
                cursor.execute(self._LATEST_SQL)
                row = cursor.fetchone()
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            raise RepositoryError("Schwellensatz konnte nicht gelesen werden") from exc
        if row is None:
            return None
        try:
            return self._row_to_threshold_set(row)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise RepositoryError(f"Schwellensatz konnte nicht gelesen werden: {exc}") from exc

    def append(self, threshold_set: ThresholdSet, audit_entry: AuditLogEntry) -> int:
        params_json = _dumps_or_repo_error(threshold_set.params, "threshold_set.params")
        try:
            with transaction(self._config) as conn, conn.cursor() as cursor:
                cursor.execute(
                    self._INSERT_SQL,
                    (
                        threshold_set.name,
                        params_json,
                        threshold_set.valid_from,
                        threshold_set.changed_by,
                    ),
                )
                new_id = cursor.lastrowid
                if not new_id:
                    # Kein AUTO_INCREMENT -> im Transaktionsblock werfen erzwingt Rollback,
                    # damit kein Satz ohne ID und ohne Audit-Eintrag zurueckbleibt (NF-01).
                    raise RepositoryError(
                        "INSERT lieferte keine gueltige ID "
                        "(AUTO_INCREMENT auf 'threshold_set' pruefen)"
                    )
                # Audit-Eintrag in DERSELBEN Transaktion ueber die kanonische Audit-Schreibform
                # (kein dupliziertes SQL, Schemaaenderung an audit_log nur an einer Stelle):
                # an die gerade vergebene Satz-ID binden (NF-09-Atomaritaet).
                MySqlAuditRepository._write_entry(
                    cursor, audit_entry.model_copy(update={"entity_id": new_id})
                )
        except RepositoryError:
            # Bereits eine Domaenen-Exception (z. B. fehlende ID, nicht serialisierbares
            # Audit-Detail) -> unveraendert weiter.
            raise
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            raise RepositoryError("Schwellensatz konnte nicht gespeichert werden") from exc
        return int(new_id)

    @staticmethod
    def _row_to_threshold_set(row: dict[str, Any]) -> ThresholdSet:
        valid_from = row["valid_from"]
        if valid_from.tzinfo is None:
            # DB speichert UTC zeitzonenlos -> tzinfo nachziehen (analog Reading/Assessment).
            valid_from = valid_from.replace(tzinfo=UTC)
        params = row["params"]
        if isinstance(params, str):
            # Je nach PyMySQL/MariaDB-Version kann eine JSON-Spalte als str kommen.
            params = json.loads(params)
        return ThresholdSet(
            id=row["id"],
            name=row["name"],
            params=params,
            valid_from=valid_from,
            changed_by=row["changed_by"],
        )


def _dumps_or_repo_error(value: object, label: str) -> str:
    """`json.dumps` mit Fail-safe: nicht serialisierbare Werte -> RepositoryError.

    Verhindert, dass ein nicht-serialisierbarer Wert den Schreibpfad mit einem rohen
    TypeError crasht (NF-01); der Aufrufer kann fail-safe reagieren.
    """
    try:
        return json.dumps(value)
    except TypeError as exc:
        raise RepositoryError(f"{label} ist nicht JSON-serialisierbar: {exc}") from exc
