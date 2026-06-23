"""Repository-Interface fuer die Persistenzschicht (Backend-Konzept §4, E-35).

Das Interface ist DB-agnostisch: der Poller (src/ingest/) arbeitet ausschliesslich
dagegen. Die konkrete MySQL-Implementierung mit PyMySQL kommt in DTB-28.
"""

from abc import ABC, abstractmethod

from src.model.schemas import Reading


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
