"""Repository-Interface und PyMySQL-Implementierung (Backend-Konzept §4, E-35).

Das Interface ist DB-agnostisch: der Poller (src/ingest/) arbeitet ausschliesslich
dagegen. Die konkrete MySQL-Implementierung nutzt rohes PyMySQL mit ausschliesslich
parametrisierten Queries (Injection-Schutz).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

import pymysql

from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.database import (
    DatabaseConfigError,
    DatabaseConnectionError,
    get_connection,
)


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
        """
        ...


class ReadingRepository(Repository):
    """PyMySQL-Implementierung des Reading-Repositories.

    Alle Queries sind parametrisiert. Zeitstempel werden als UTC gespeichert und
    zurueckgegeben. Bei Datenbankfehlern wird eine RepositoryError geworfen.

    Args:
        connection: Optional bestehende PyMySQL-Verbindung (z. B. fuer Tests).
            Wird keine uebergeben, oeffnet jede Operation per get_connection()
            eine kurzlebige Verbindung aus den Umgebungsvariablen.
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
    """

    def __init__(self, connection: pymysql.Connection | None = None) -> None:
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
            raise RepositoryError(
                f"Reading konnte nicht gespeichert werden: {exc}"
            ) from exc

    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        """Liefert die neuesten Readings eines Sensors, absteigend nach measured_at.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
        """
        return self._execute_read(self._LATEST_SQL, (sensor_id, limit))

    def get_since(self, sensor_id: str, since: datetime) -> Sequence[Reading]:
        """Liefert alle Readings eines Sensors seit einem Zeitpunkt (inklusiv, UTC).

        Raises:
            RepositoryError: Bei Datenbankfehlern.
        """
        return self._execute_read(self._SINCE_SQL, (sensor_id, since))

    def _execute_read(self, sql: str, params: tuple) -> Sequence[Reading]:
        """Fuehrt eine Lese-Query aus und mappt Zeilen auf Reading-Objekte."""
        try:
            if self._connection is not None:
                return self._fetch(self._connection, sql, params)
            with get_connection() as conn:
                return self._fetch(conn, sql, params)
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            raise RepositoryError(
                f"Reading konnte nicht gelesen werden: {exc}"
            ) from exc

    @staticmethod
    def _insert(conn: pymysql.Connection, params: tuple) -> int:
        """Fuehrt INSERT aus, committet und gibt lastrowid zurueck."""
        try:
            with conn.cursor() as cursor:
                cursor.execute(ReadingRepository._INSERT_SQL, params)
                reading_id = cursor.lastrowid
            conn.commit()
            return reading_id  # type: ignore[return-value]
        except pymysql.Error:
            try:
                conn.rollback()
            except pymysql.Error:
                pass
            raise

    @staticmethod
    def _fetch(conn: pymysql.Connection, sql: str, params: tuple) -> Sequence[Reading]:
        """Fuehrt SELECT aus und mappt Zeilen auf Reading-Objekte."""
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return tuple(ReadingRepository._row_to_reading(row) for row in rows)

    @staticmethod
    def _row_to_reading(row: dict) -> Reading:
        """Mappt eine DB-Zeile auf ein Reading-Objekt."""
        return Reading(
            id=row["id"],
            sensor_id=row["sensor_id"],
            measured_at=row["measured_at"],
            received_at=row["received_at"],
            surface_temp_c=row["surface_temp_c"],
            air_temp_c=row["air_temp_c"],
            humidity_pct=row["humidity_pct"],
            pressure_hpa=row["pressure_hpa"],
            dew_point_c=row["dew_point_c"],
            source=Source(row["source"]),
            status=SensorStatus(row["status"]),
        )
