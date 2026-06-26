"""Persistenz fuer Bewertungen (Assessment) — DTB-64 / F10.

Gegenstueck zu ReadingRepository (DTB-28): speichert die von assess_ice_risk
erzeugten Assessment-Snapshots audit-fest in der `assessment`-Tabelle
(migrations/schema.sql) und liefert die zuletzt erzeugte Bewertung fuers
Serving (GET /v1/assessment/current, DTB-43).

DB-agnostische Naht: der AssessmentService (DTB-64) arbeitet ausschliesslich
gegen das abstrakte Interface. Rohes PyMySQL, nur parametrisierte Queries.
"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from src.model.enums import RiskLevel
from src.model.schemas import Assessment
from src.storage.database import (
    DatabaseConfigError,
    DatabaseConnectionError,
    get_connection,
)
from src.storage.repository import RepositoryError

logger = logging.getLogger(__name__)


class AssessmentRepository(ABC):
    """Abstrakte Persistenz fuer Bewertungen.

    - Trennt den AssessmentService von der konkreten Datenbank.
    - Ermoeglicht Test-Doubles (InMemoryAssessmentRepository).
    - Konkrete PyMySQL-Implementierung: MySqlAssessmentRepository.
    """

    @abstractmethod
    def save(self, assessment: Assessment) -> int:
        """Speichert eine Bewertung und gibt die generierte ID zurueck.

        Raises:
            RepositoryError: Bei Fehlern in der Persistenzschicht (Fail-safe).
        """
        ...

    @abstractmethod
    def get_latest(self) -> Assessment | None:
        """Liefert die zuletzt erzeugte Bewertung (hoechstes `ts`), sonst None.

        Wird fuer GET /v1/assessment/current (DTB-43) verwendet.

        Scope-Hinweis (Single-Sensor): liefert das GLOBAL neueste Assessment,
        nicht pro Sensor. Im aktuellen Single-Sensor-Betrieb (anr-rwy-01) korrekt.
        Bei der DTB-43-Haertung auf Multi-Sensor MUSS nach sensor_id/reading_id
        gefiltert werden, sonst kann ein Assessment von Sensor B mit dem Reading
        von Sensor A gepaart und ein inkonsistenter Snapshot ausgeliefert werden.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
        """
        ...


class InMemoryAssessmentRepository(AssessmentRepository):
    """In-Memory-Double fuer Tests und lokale Laeufe (keine DB noetig).

    Vergibt fortlaufende IDs ab 1 und merkt sich die Bewertungen in
    Einfuege-Reihenfolge. `get_latest` liefert die mit dem hoechsten `ts`.
    """

    def __init__(self) -> None:
        self._items: list[Assessment] = []

    def save(self, assessment: Assessment) -> int:
        new_id = len(self._items) + 1
        self._items.append(assessment.model_copy(update={"id": new_id}))
        return new_id

    def get_latest(self) -> Assessment | None:
        if not self._items:
            return None
        # Hoechstes ts gewinnt; bei Gleichstand die spaeter eingefuegte (groessere id).
        return max(self._items, key=lambda a: (a.ts, a.id or 0))


class MySqlAssessmentRepository(AssessmentRepository):
    """PyMySQL-Implementierung des Assessment-Repositories (DTB-64, E-35).

    Alle Queries sind parametrisiert. Zeitstempel werden als UTC gespeichert und
    zurueckgegeben. Bei Datenbankfehlern wird RepositoryError geworfen, damit der
    Aufrufer fail-safe reagieren kann (NF-01).

    Args:
        connection: Optional bestehende PyMySQL-Verbindung (z. B. fuer Tests).
            Wird keine uebergeben, oeffnet jede Operation eine kurzlebige
            Verbindung aus den Umgebungsvariablen. Eine uebergebene Verbindung
            MUSS einen DictCursor verwenden, sonst scheitert das Row-Mapping.
    """

    _INSERT_SQL = """
        INSERT INTO assessment (
            ts, reading_id, threshold_set_id, risk_level,
            driving_factor, explanation,
            surface_temp_c, dew_point_c, delta_t, humidity_pct
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """

    # Scope: global neuestes Assessment (nicht pro Sensor) — Single-Sensor-OK.
    # DTB-43-Haertung fuer Multi-Sensor: WHERE sensor_id/reading_id ergaenzen.
    _LATEST_SQL = """
        SELECT
            id, ts, reading_id, threshold_set_id, risk_level,
            driving_factor, explanation,
            surface_temp_c, dew_point_c, delta_t, humidity_pct
        FROM assessment
        ORDER BY ts DESC, id DESC
        LIMIT 1
    """

    def __init__(self, connection: pymysql.Connection | None = None) -> None:
        if connection is not None:
            cursorclass = getattr(connection, "cursorclass", None)
            if not (isinstance(cursorclass, type) and issubclass(cursorclass, DictCursor)):
                raise ValueError(
                    "MySqlAssessmentRepository benoetigt eine Verbindung mit DictCursor "
                    "(cursorclass=pymysql.cursors.DictCursor)."
                )
        self._connection = connection

    def save(self, assessment: Assessment) -> int:
        params = (
            assessment.ts,
            assessment.reading_id,
            assessment.threshold_set_id,
            str(assessment.risk_level),
            assessment.driving_factor,
            assessment.explanation,
            assessment.surface_temp_c,
            assessment.dew_point_c,
            assessment.delta_t,
            assessment.humidity_pct,
        )
        try:
            if self._connection is not None:
                return self._insert(self._connection, params)
            with get_connection() as conn:
                return self._insert(conn, params)
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            raise RepositoryError(f"Assessment konnte nicht gespeichert werden: {exc}") from exc

    def get_latest(self) -> Assessment | None:
        try:
            if self._connection is not None:
                return self._fetch_latest(self._connection)
            with get_connection() as conn:
                return self._fetch_latest(conn)
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            raise RepositoryError(f"Assessment konnte nicht gelesen werden: {exc}") from exc

    @staticmethod
    def _insert(conn: pymysql.Connection, params: tuple) -> int:
        try:
            with conn.cursor() as cursor:
                cursor.execute(MySqlAssessmentRepository._INSERT_SQL, params)
                assessment_id = cursor.lastrowid
            # ID-Pruefung VOR commit: bei fehlender/ungueltiger ID (theoretischer
            # AUTO_INCREMENT-Fehlerfall) wird die Zeile verworfen statt persistiert,
            # damit keine Orphan-Row ohne zurueckgegebene ID und ohne Assessment-
            # Snapshot zurueckbleibt (NF-01: konsistenter Zustand; der Service
            # behandelt den Zyklus als fehlgeschlagen statt halb persistiert).
            # `not` faengt None UND 0 ab (0 = kein AUTO_INCREMENT / unerwarteter
            # MySQL-Zustand); eine gueltige Auto-ID ist immer >= 1.
            if not assessment_id:
                conn.rollback()
                raise RepositoryError(
                    "INSERT lieferte keine gueltige ID (AUTO_INCREMENT auf 'assessment' pruefen)"
                )
            conn.commit()
            return assessment_id
        except pymysql.Error:
            try:
                conn.rollback()
            except pymysql.Error as rollback_exc:
                # Rollback-Fehler nicht still schlucken (analog ReadingRepository).
                logger.error("DB-Rollback nach INSERT-Fehler fehlgeschlagen: %s", rollback_exc)
            raise

    @staticmethod
    def _fetch_latest(conn: pymysql.Connection) -> Assessment | None:
        with conn.cursor() as cursor:
            cursor.execute(MySqlAssessmentRepository._LATEST_SQL)
            row = cursor.fetchone()
        if row is None:
            return None
        try:
            return MySqlAssessmentRepository._row_to_assessment(row)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise RepositoryError(f"Assessment konnte nicht gelesen werden: {exc}") from exc

    @staticmethod
    def _row_to_assessment(row: dict[str, Any]) -> Assessment:
        ts = row["ts"]
        if ts.tzinfo is None:
            # DB speichert UTC zeitzonenlos -> tzinfo nachziehen (analog Reading).
            ts = ts.replace(tzinfo=UTC)
        return Assessment(
            id=row["id"],
            ts=ts,
            reading_id=row["reading_id"],
            threshold_set_id=row["threshold_set_id"],
            risk_level=RiskLevel(row["risk_level"]),
            driving_factor=row["driving_factor"],
            explanation=row["explanation"],
            surface_temp_c=row["surface_temp_c"],
            dew_point_c=row["dew_point_c"],
            delta_t=row["delta_t"],
            humidity_pct=row["humidity_pct"],
        )
