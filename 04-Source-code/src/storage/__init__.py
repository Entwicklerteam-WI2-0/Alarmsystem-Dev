"""Storage: DB-Zugriff (Repository-Pattern).

Rohes PyMySQL -> MySQL/MariaDB; kein ORM, E-35.
Siehe Backend-Konzept §6a.
"""

from src.storage.assessment_repository import (
    AssessmentRepository,
    InMemoryAssessmentRepository,
    MySqlAssessmentRepository,
)
from src.storage.audit_repository import (
    AuditRepository,
    InMemoryAuditRepository,
    MySqlAuditRepository,
)
from src.storage.database import get_connection
from src.storage.repository import (
    InMemoryReadingRepository,
    ReadingRepository,
    Repository,
    RepositoryError,
)
from src.storage.threshold_set_repository import (
    InMemoryThresholdSetRepository,
    MySqlThresholdSetRepository,
    ThresholdSetRepository,
)

__all__ = [
    "get_connection",
    "InMemoryReadingRepository",
    "ReadingRepository",
    "Repository",
    "RepositoryError",
    # Assessment-Persistenz (DTB-64 / F10):
    "AssessmentRepository",
    "InMemoryAssessmentRepository",
    "MySqlAssessmentRepository",
    # Audit-Log (DTB-29):
    "AuditRepository",
    "InMemoryAuditRepository",
    "MySqlAuditRepository",
    # Schwellensatz-Versionierung (DTB-63 / DTB-54):
    "ThresholdSetRepository",
    "InMemoryThresholdSetRepository",
    "MySqlThresholdSetRepository",
]
