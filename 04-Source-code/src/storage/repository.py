"""Repository-Interface und PyMySQL-Implementierung (Backend-Konzept §4, E-35).

Das Interface ist DB-agnostisch: der Poller (src/ingest/) arbeitet ausschliesslich
dagegen. Die konkrete MySQL-Implementierung nutzt rohes PyMySQL mit ausschliesslich
parametrisierten Queries (Injection-Schutz).
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

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


def _validate_get_between_args(
    from_dt: datetime | None,
    to_dt: datetime | None,
    limit: int,
    offset: int,
) -> None:
    """Validiert die gemeinsamen Argumente fuer Repository.get_between.

    Zentralisiert, damit InMemoryReadingRepository und ReadingRepository
    identische Regeln erzwingen (MEDIUM-Review-Finding DTB-34).
    Fehlermeldungen nutzen die API-Parameternamen 'from'/'to', weil
    ValueError aus dem Repository direkt an den Client weitergegeben wird.
    """
    if from_dt is not None and from_dt.tzinfo is None:
        raise ValueError("'from' muss zeitzonenbewusst sein (UTC)")
    if to_dt is not None and to_dt.tzinfo is None:
        raise ValueError("'to' muss zeitzonenbewusst sein (UTC)")
    if from_dt is not None and to_dt is not None and from_dt > to_dt:
        raise ValueError("'from' darf nicht nach 'to' liegen")
    if limit <= 0:
        raise ValueError(f"limit muss positiv sein, erhalten: {limit}")
    if offset < 0:
        raise ValueError(f"offset darf nicht negativ sein, erhalten: {offset}")


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
            Sequenz der Readings, aufsteigend nach measured_at. Ueberschreitet das
            Zeitfenster `limit` Readings, werden die FRISCHESTEN `limit` behalten (die
            aeltesten fallen raus) — relevant fuer die Trend-Extrapolation (DTB-33).
            Leere Sequenz, wenn keine vorhanden sind.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
            ValueError: Wenn since nicht zeitzonenbewusst ist (UTC).
        """
        ...

    @abstractmethod
    def get_between(
        self,
        sensor_id: str,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        order: Literal["asc", "desc"] = "desc",
    ) -> Sequence[Reading]:
        """Liefert Readings eines Sensors in einem Zeitfenster (inklusiv, UTC).

        Args:
            sensor_id: Sensor-ID, fuer die die Readings gesucht werden.
            from_dt: Untere Zeitschranke (inklusiv) fuer measured_at. None = unbeschraenkt.
            to_dt: Obere Zeitschranke (inklusiv) fuer measured_at. None = unbeschraenkt.
            limit: Maximale Anzahl zurueckzugebender Readings (Default: 100).
            offset: Anzahl zu ueberspringender Zeilen (Default: 0).
            order: Sortierung nach measured_at ('asc' oder 'desc', Default: 'desc').

        Returns:
            Sequenz der Readings, sortiert nach `order`.
            Leere Sequenz, wenn keine vorhanden sind.

        Raises:
            RepositoryError: Bei Datenbankfehlern.
            ValueError: Wenn from_dt/to_dt nicht zeitzonenbewusst sind,
                from_dt nach to_dt liegt, limit nicht positiv ist
                oder offset negativ ist.
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
        # Bei LIMIT-Ueberschreitung die FRISCHESTEN behalten (analog _SINCE_SQL: innere
        # DESC-LIMIT-Subquery), dann aufsteigend zurueckgeben (aeussere ASC-Sortierung).
        newest = sorted(candidates, key=lambda r: (r.measured_at, r.id or 0), reverse=True)[:limit]
        ordered = sorted(newest, key=lambda r: (r.measured_at, r.id or 0))
        return tuple(ordered)

    def get_between(
        self,
        sensor_id: str,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        order: Literal["asc", "desc"] = "desc",
    ) -> Sequence[Reading]:
        _validate_get_between_args(from_dt, to_dt, limit, offset)

        candidates = [r for r in self._items if r.sensor_id == sensor_id]
        if from_dt is not None:
            candidates = [r for r in candidates if r.measured_at >= from_dt]
        if to_dt is not None:
            candidates = [r for r in candidates if r.measured_at <= to_dt]

        reverse = order == "desc"
        ordered = sorted(candidates, key=lambda r: (r.measured_at, r.id or 0), reverse=reverse)
        return tuple(ordered[offset : offset + limit])


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

    # Bei LIMIT-Ueberschreitung die FRISCHESTEN Readings behalten (fuer die Trend-
    # Extrapolation relevantesten): innere Subquery kappt absteigend (neueste zuerst),
    # die aeussere Sortierung stellt den dokumentierten ASC-Rueckgabevertrag wieder her.
    # Ein blosses ASC+LIMIT haette bei Ueberschreitung die AELTESTEN geliefert und den
    # juengsten Trend still verworfen (DTB-33 Review MEDIUM). Tritt mit der aktuellen
    # Config (poll 30 s, max_readings_limit 1000) nicht ein, ist aber kadenz-robust.
    _SINCE_SQL = """
        SELECT * FROM (
            SELECT
                id, sensor_id, measured_at, received_at,
                surface_temp_c, air_temp_c, humidity_pct,
                pressure_hpa, dew_point_c, source, status
            FROM reading
            WHERE sensor_id = %s AND measured_at >= %s
            ORDER BY measured_at DESC, id DESC
            LIMIT %s
        ) AS recent
        ORDER BY measured_at ASC, id ASC
    """

    _SELECT_SQL = """
        SELECT
            id, sensor_id, measured_at, received_at,
            surface_temp_c, air_temp_c, humidity_pct,
            pressure_hpa, dew_point_c, source, status
        FROM reading
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

    def get_between(
        self,
        sensor_id: str,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        order: Literal["asc", "desc"] = "desc",
    ) -> Sequence[Reading]:
        """Liefert Readings eines Sensors in einem Zeitfenster (inklusiv, UTC).

        Raises:
            RepositoryError: Bei Datenbankfehlern.
            ValueError: Bei ungueltigen Zeitstempeln, from > to,
                nicht-positivem limit oder negativem offset.
        """
        _validate_get_between_args(from_dt, to_dt, limit, offset)

        conditions = ["sensor_id = %s"]
        params: list[Any] = [sensor_id]
        if from_dt is not None:
            conditions.append("measured_at >= %s")
            params.append(from_dt)
        if to_dt is not None:
            conditions.append("measured_at <= %s")
            params.append(to_dt)

        order_clause = (
            "ORDER BY measured_at DESC, id DESC"
            if order == "desc"
            else "ORDER BY measured_at ASC, id ASC"
        )
        # WHERE-Fragmente sind feste Strings; nur Werte kommen aus params -> parametrisiert.
        where_clause = " AND ".join(conditions)
        sql = f"{self._SELECT_SQL} WHERE {where_clause} {order_clause} LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        return self._execute_read(sql, tuple(params))

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
