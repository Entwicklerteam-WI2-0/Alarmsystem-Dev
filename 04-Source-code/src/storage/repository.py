"""Repository-Interface und PyMySQL-Implementierung (Backend-Konzept §4, E-35).

Das Interface ist DB-agnostisch: der Poller (src/ingest/) arbeitet ausschliesslich
dagegen. Die konkrete MySQL-Implementierung nutzt rohes PyMySQL mit ausschliesslich
parametrisierten Queries (Injection-Schutz).
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.database import (
    DatabaseConfigError,
    DatabaseConnectionError,
    get_connection,
)

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Domänen-Exception für Fehler in der Persistenzschicht.

    Der Poller fängt diese ab und geht fail-safe (kein Speichern, kein GRÜN).
    Konkrete Implementierungen (z. B. PyMySQL in DTB-28) leiten ihre Fehler
    auf diese Exception herunter.
    """


class Repository(ABC):
    """Abstrakte Persistenz-Schicht fuer Readings.

    - Trennt den Poller von der konkreten Datenbank.
    - Ermoeglicht Test-Doubles (z. B. In-Memory-Stub).
    - Konkrete PyMySQL-Implementierung: ReadingRepository.
    """

    @abstractmethod
    def save(self, reading: Reading) -> int:
        """Speichert ein Reading und gibt die generierte ID zurueck.

        Args:
            reading: Das zu speichernde Reading-Objekt (DTB-12).

        Returns:
            Die vom Speichermedium vergebene ID (z. B. AUTO_INCREMENT).
        """
        ...

    @abstractmethod
    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        """Liefert die neuesten Readings eines Sensors.

        Wird u. a. fuer die Stale-Erkennung (DTB-13) verwendet: Aufrufer
        pruefen `result[0]` falls vorhanden, sonst liegen noch keine Daten vor.
        Bei einem Fehler in der Persistenzschicht wird RepositoryError geworfen
        -> separater Fail-safe-Fall gegenueber "Sensor liefert keine aktuellen
        Daten" (NF-01/E-34).

        Args:
            sensor_id: Sensor-ID, fuer die die neuesten Readings gesucht werden.
            limit: Maximale Anzahl zurueckzugebender Readings (Default: 1).

        Returns:
            Sequenz der neuesten Readings, absteigend nach measured_at.
            Leere Sequenz, wenn noch keines vorhanden ist.

        Raises:
            ValueError: Wenn limit nicht positiv ist.
        """
        ...

    @abstractmethod
    def get_since(self, sensor_id: str, since: datetime, limit: int = 1000) -> Sequence[Reading]:
        """Liefert Readings eines Sensors seit einem Zeitpunkt (inklusiv, UTC).

        Args:
            sensor_id: Sensor-ID, fuer die die Readings gesucht werden.
            since: Untere Zeitschranke (inklusiv) fuer measured_at.
            limit: Maximale Anzahl zurueckzugebender Readings (Default: 1000).

        Returns:
            Sequenz der Readings, aufsteigend nach measured_at.
            Leere Sequenz, wenn keine vorhanden sind.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
            ValueError: Wenn since nicht zeitzonenbewusst ist (UTC).
        """
        ...


class InMemoryReadingRepository(Repository):
    """In-Memory-Double fuer Tests und lokale Laeufe (keine DB noetig).

    Gegenstueck zu InMemoryAssessmentRepository: vergibt fortlaufende IDs ab 1 und
    legt eine Kopie MIT id ab (model_copy), damit das gespeicherte Objekt nicht mit
    dem uebergebenen aliased (copy-on-write, keine Mutation). Spiegelt die Sortier-
    Semantik der PyMySQL-Implementierung (ReadingRepository): get_latest absteigend
    nach (measured_at, id), get_since aufsteigend.
    """

    def __init__(self) -> None:
        self._items: list[Reading] = []

    def save(self, reading: Reading) -> int:
        new_id = len(self._items) + 1
        # Kopie MIT id ablegen; das uebergebene Original bleibt unveraendert.
        self._items.append(reading.model_copy(update={"id": new_id}))
        return new_id

    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        if limit <= 0:
            raise ValueError(f"limit muss positiv sein, erhalten: {limit}")
        candidates = [r for r in self._items if r.sensor_id == sensor_id]
        # Absteigend nach measured_at, bei Gleichstand nach id (analog _LATEST_SQL:
        # ORDER BY measured_at DESC, id DESC).
        ordered = sorted(candidates, key=lambda r: (r.measured_at, r.id or 0), reverse=True)
        return tuple(ordered[:limit])

    def get_since(self, sensor_id: str, since: datetime, limit: int = 1000) -> Sequence[Reading]:
        if since.tzinfo is None:
            raise ValueError("since muss zeitzonenbewusst sein (UTC)")
        if limit <= 0:
            raise ValueError(f"limit muss positiv sein, erhalten: {limit}")
        candidates = [r for r in self._items if r.sensor_id == sensor_id and r.measured_at >= since]
        # Aufsteigend nach measured_at, bei Gleichstand nach id (analog _SINCE_SQL:
        # ORDER BY measured_at ASC, id ASC).
        ordered = sorted(candidates, key=lambda r: (r.measured_at, r.id or 0))
        return tuple(ordered[:limit])


class ReadingRepository(Repository):
    """PyMySQL-Implementierung des Reading-Repositories.

    Alle Queries sind parametrisiert. Zeitstempel werden als UTC gespeichert und
    zurueckgegeben. Bei Datenbankfehlern wird eine RepositoryError geworfen.

    Args:
        connection: Optional bestehende PyMySQL-Verbindung (z. B. fuer Tests).
            Wird keine uebergeben, oeffnet jede Operation per get_connection()
            eine kurzlebige Verbindung aus den Umgebungsvariablen. Eine
            uebergebene Verbindung MUSS einen DictCursor verwenden
            (cursorclass=pymysql.cursors.DictCursor), sonst liefert PyMySQL
            Tupel statt Dicts und _row_to_reading scheitert.
    """

    _INSERT_SQL = """
        INSERT INTO reading (
            sensor_id, measured_at, received_at,
            surface_temp_c, air_temp_c, humidity_pct,
            pressure_hpa, dew_point_c, source, status
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """

    _LATEST_SQL = """
        SELECT
            id, sensor_id, measured_at, received_at,
            surface_temp_c, air_temp_c, humidity_pct,
            pressure_hpa, dew_point_c, source, status
        FROM reading
        WHERE sensor_id = %s
        ORDER BY measured_at DESC, id DESC
        LIMIT %s
    """

    _SINCE_SQL = """
        SELECT
            id, sensor_id, measured_at, received_at,
            surface_temp_c, air_temp_c, humidity_pct,
            pressure_hpa, dew_point_c, source, status
        FROM reading
        WHERE sensor_id = %s AND measured_at >= %s
        ORDER BY measured_at ASC, id ASC
        LIMIT %s
    """

    def __init__(self, connection: pymysql.Connection | None = None) -> None:
        # Fail-fast statt stillem Contract-Bruch: eine injizierte Verbindung ohne
        # DictCursor wuerde Tupel liefern, woraufhin _row_to_reading bei jedem Read
        # scheitert und das als RepositoryError maskiert wird (DTB-93 MEDIUM). Lieber
        # hier laut scheitern als spaeter verschleiert. get_connection() (Default-Pfad)
        # erzwingt DictCursor bereits.
        if connection is not None:
            cursorclass = getattr(connection, "cursorclass", None)
            if not (isinstance(cursorclass, type) and issubclass(cursorclass, DictCursor)):
                raise ValueError(
                    "ReadingRepository benoetigt eine Verbindung mit DictCursor "
                    "(cursorclass=pymysql.cursors.DictCursor)."
                )
        self._connection = connection

    def save(self, reading: Reading) -> int:
        """Speichert ein Reading und gibt die generierte ID zurueck.

        Raises:
            RepositoryError: Bei Verbindungs-, Konfigurations- oder SQL-Fehlern.
        """
        params = (
            reading.sensor_id,
            reading.measured_at,
            reading.received_at,
            reading.surface_temp_c,
            reading.air_temp_c,
            reading.humidity_pct,
            reading.pressure_hpa,
            reading.dew_point_c,
            str(reading.source),
            str(reading.status),
        )
        try:
            if self._connection is not None:
                return self._insert(self._connection, params)
            with get_connection() as conn:
                return self._insert(conn, params)
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            raise RepositoryError(f"Reading konnte nicht gespeichert werden: {exc}") from exc

    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        """Liefert die neuesten Readings eines Sensors, absteigend nach measured_at.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
            ValueError: Wenn limit nicht positiv ist.
        """
        if limit <= 0:
            raise ValueError(f"limit muss positiv sein, erhalten: {limit}")
        return self._execute_read(self._LATEST_SQL, (sensor_id, limit))

    def get_since(self, sensor_id: str, since: datetime, limit: int = 1000) -> Sequence[Reading]:
        """Liefert Readings eines Sensors seit einem Zeitpunkt (inklusiv, UTC).

        Raises:
            RepositoryError: Bei Datenbankfehlern.
            ValueError: Wenn since nicht zeitzonenbewusst ist oder limit nicht positiv ist.
        """
        if since.tzinfo is None:
            raise ValueError("since muss zeitzonenbewusst sein (UTC)")
        if limit <= 0:
            raise ValueError(f"limit muss positiv sein, erhalten: {limit}")
        return self._execute_read(self._SINCE_SQL, (sensor_id, since, limit))

    def _execute_read(self, sql: str, params: tuple) -> Sequence[Reading]:
        """Fuehrt eine Lese-Query aus und mappt Zeilen auf Reading-Objekte."""
        try:
            if self._connection is not None:
                return self._fetch(self._connection, sql, params)
            with get_connection() as conn:
                return self._fetch(conn, sql, params)
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            raise RepositoryError(f"Reading konnte nicht gelesen werden: {exc}") from exc

    @staticmethod
    def _insert(conn: pymysql.Connection, params: tuple) -> int:
        """Fuehrt INSERT aus, prueft die ID VOR dem commit und gibt lastrowid zurueck.

        Reihenfolge ID-Check vor commit bewusst: bei fehlender/ungueltiger ID
        (theoretischer AUTO_INCREMENT-Fehlerfall) wird die Zeile verworfen statt
        persistiert, damit keine Orphan-Row ohne zurueckgegebene ID zurueckbleibt
        (NF-01: konsistenter Zustand). Entspricht MySqlAssessmentRepository._insert.
        """
        try:
            with conn.cursor() as cursor:
                cursor.execute(ReadingRepository._INSERT_SQL, params)
                reading_id = cursor.lastrowid
            # `not` faengt None UND 0 ab (0 = kein AUTO_INCREMENT / unerwarteter
            # MySQL-Zustand); eine gueltige Auto-ID ist immer >= 1.
            if not reading_id:
                conn.rollback()
                raise RepositoryError(
                    "INSERT lieferte keine gueltige ID (AUTO_INCREMENT auf 'reading' pruefen)"
                )
            conn.commit()
            return reading_id
        except pymysql.Error:
            try:
                conn.rollback()
            except pymysql.Error as rollback_exc:
                # Rollback-Fehler nicht still schlucken: fuer den Betrieb sichtbar machen
                # (analog database.transaction). Die urspruengliche Exception wird
                # unveraendert weitergeworfen (DTB-93 MEDIUM).
                logger.error("DB-Rollback nach INSERT-Fehler fehlgeschlagen: %s", rollback_exc)
            raise

    @staticmethod
    def _fetch(conn: pymysql.Connection, sql: str, params: tuple) -> Sequence[Reading]:
        """Fuehrt SELECT aus und mappt Zeilen auf Reading-Objekte.

        ValueError aus _row_to_reading (z. B. ungueltiger Enum-Wert nach
        DB-Korruption/Migration) wird in RepositoryError umgewandelt, damit
        der Vertrag des Repository-Interface eingehalten wird.
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        try:
            return tuple(ReadingRepository._row_to_reading(row) for row in rows)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            # Vollstaendige Menge der erwartbaren Mapping-Fehler bei Schema-Drift/
            # DB-Korruption -> alle fail-safe als RepositoryError (Interface-Vertrag):
            # - ValueError: ungueltiger Enum-Wert (auch Pydantic ValidationError erbt davon).
            # - KeyError: fehlende Spalte.
            # - TypeError: falscher Cursor-Typ (Tupel statt Dict).
            # - AttributeError: Spaltenwert mit falschem Typ, z. B. str statt datetime,
            #   sodass row["measured_at"].tzinfo fehlschlaegt (DTB-93 MEDIUM).
            raise RepositoryError(f"Reading konnte nicht gelesen werden: {exc}") from exc

    @staticmethod
    def _row_to_reading(row: dict[str, Any]) -> Reading:
        """Mappt eine DB-Zeile auf ein Reading-Objekt.

        PyMySQL liefert DATETIME-Spalten als naive datetime-Objekte ohne
        tzinfo. Da die DB ausschliesslich UTC speichert, wird tzinfo=UTC
        gesetzt, damit Zeitstempelvergleiche (z. B. is_stale in DTB-38)
        nicht zwischen offset-naive und offset-aware werfen.
        """
        measured_at = row["measured_at"]
        if measured_at.tzinfo is None:
            measured_at = measured_at.replace(tzinfo=UTC)
        received_at = row["received_at"]
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=UTC)

        return Reading(
            id=row["id"],
            sensor_id=row["sensor_id"],
            measured_at=measured_at,
            received_at=received_at,
            surface_temp_c=row["surface_temp_c"],
            air_temp_c=row["air_temp_c"],
            humidity_pct=row["humidity_pct"],
            pressure_hpa=row["pressure_hpa"],
            dew_point_c=row["dew_point_c"],
            source=Source(row["source"]),
            status=SensorStatus(row["status"]),
        )
