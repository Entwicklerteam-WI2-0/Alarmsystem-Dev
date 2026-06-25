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
from src.storage.database import get_connection


class RepositoryError(Exception):
    """Domänen-Exception fuer Fehler in der Persistenzschicht.

    Der Poller faengt diese ab und geht fail-safe (kein Speichern, kein GRUEN).
    Konkrete Implementierungen leiten ihre Fehler auf diese Exception herunter.
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


class ReadingRepository(Repository):
    """PyMySQL-Implementierung des Reading-Repositories.

    Alle Queries sind parametrisiert. Zeitstempel werden als UTC gespeichert und
    zurueckgegeben. Bei Datenbankfehlern wird eine RepositoryError geworfen.
    """

    def __init__(self, connection: pymysql.Connection | None = None) -> None:
        """Initialisiert das Repository.

        Args:
            connection: Optional bestehende PyMySQL-Verbindung. Wird keine
                uebergeben, oeffnet save() fuer jede Operation eine neue
                Verbindung und schliesst sie wieder.
        """
        self._connection = connection

    def _get_connection(self) -> pymysql.Connection:
        """Liefert die bestehende oder eine neue Verbindung."""
        if self._connection is not None:
            return self._connection
        return get_connection()

    def save(self, reading: Reading) -> int:
        """Speichert ein Reading und gibt die generierte ID zurueck.

        Args:
            reading: Das zu speichernde Reading-Objekt.

        Returns:
            Die vom Speichermedium vergebene ID.

        Raises:
            RepositoryError: Bei Datenbank- oder Konvertierungsfehlern.
        """
        sql = """
            INSERT INTO reading (
                sensor_id, measured_at, received_at,
                surface_temp_c, air_temp_c, humidity_pct,
                pressure_hpa, dew_point_c, source, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
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

        conn: pymysql.Connection | None = None
        own_connection = self._connection is None
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                reading_id = cursor.lastrowid
            conn.commit()
            return reading_id  # type: ignore[return-value]
        except pymysql.Error as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except pymysql.Error:
                    pass
            raise RepositoryError(f"Reading konnte nicht gespeichert werden: {exc}") from exc
        finally:
            if own_connection and conn is not None:
                conn.close()

    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        """Liefert die neuesten Readings eines Sensors.

        Args:
            sensor_id: ID des Sensors.
            limit: Maximale Anzahl Ergebnisse (default 1).

        Returns:
            Sequenz von Reading-Objekten, absteigend nach measured_at sortiert.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
        """
        sql = """
            SELECT
                id, sensor_id, measured_at, received_at,
                surface_temp_c, air_temp_c, humidity_pct,
                pressure_hpa, dew_point_c, source, status
            FROM reading
            WHERE sensor_id = %s
            ORDER BY measured_at DESC, id DESC
            LIMIT %s
        """
        return self._execute_read(sql, (sensor_id, limit))

    def get_since(self, sensor_id: str, since: datetime) -> Sequence[Reading]:
        """Liefert alle Readings eines Sensors seit einem Zeitpunkt.

        Args:
            sensor_id: ID des Sensors.
            since: Zeitstempel (inklusiv), ab dem gelesen wird (UTC).

        Returns:
            Sequenz von Reading-Objekten, aufsteigend nach measured_at sortiert.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
        """
        sql = """
            SELECT
                id, sensor_id, measured_at, received_at,
                surface_temp_c, air_temp_c, humidity_pct,
                pressure_hpa, dew_point_c, source, status
            FROM reading
            WHERE sensor_id = %s AND measured_at >= %s
            ORDER BY measured_at ASC, id ASC
        """
        return self._execute_read(sql, (sensor_id, since))

    def _execute_read(self, sql: str, params: tuple) -> Sequence[Reading]:
        """Fuehrt eine Lese-Query aus und mappt Zeilen auf Reading-Objekte."""
        conn: pymysql.Connection | None = None
        own_connection = self._connection is None
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            return tuple(self._row_to_reading(row) for row in rows)
        except pymysql.Error as exc:
            raise RepositoryError(f"Reading konnte nicht gelesen werden: {exc}") from exc
        finally:
            if own_connection and conn is not None:
                conn.close()

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
