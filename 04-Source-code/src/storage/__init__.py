"""Storage: DB-Zugriff (Repository-Pattern).

Rohes PyMySQL -> MySQL/MariaDB; kein ORM, E-35.
Siehe Backend-Konzept §6a.
"""

from src.storage.database import connection, get_connection
from src.storage.repository import ReadingRepository, Repository, RepositoryError

__all__ = [
    "connection",
    "get_connection",
    "ReadingRepository",
    "Repository",
    "RepositoryError",
]
