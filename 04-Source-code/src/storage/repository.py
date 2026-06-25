"""Repository-Interface fuer die Persistenzschicht (Backend-Konzept §4, E-35).

Das Interface ist DB-agnostisch: der Poller (src/ingest/) arbeitet ausschliesslich
dagegen. Die konkrete MySQL-Implementierung mit PyMySQL kommt in DTB-28.
"""

from abc import ABC, abstractmethod

from src.model.schemas import Reading


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
    - Konkrete PyMySQL-Implementierung folgt in DTB-28.
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
    def get_latest(self, sensor_id: str) -> Reading | None:
        """Liefert das neueste Reading eines Sensors oder None.

        Wird fuer die Stale-Erkennung (DTB-13) verwendet. Bei einem Fehler in der
        Persistenzschicht wird RepositoryError geworfen -> separater Fail-safe-Fall
        gegenueber "Sensor liefert keine aktuellen Daten" (NF-01/E-34).

        Args:
            sensor_id: Sensor-ID, fuer die das neueste Reading gesucht wird.

        Returns:
            Das neueste Reading oder None, wenn noch keines vorhanden ist.
        """
        ...
