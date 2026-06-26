"""Model: Pydantic-Schemas + Enums (reading, assessment, alarm, ...) — Backend-Konzept §4, DTB-12.

Persistenz-DDL (handgeschrieben, kein ORM): migrations/schema.sql (E-35). Alle Zeitstempel UTC.
"""

from .enums import (
    AlarmSeverity,
    AlarmState,
    AuditEventType,
    RiskLevel,
    SensorStatus,
    Source,
)
from .schemas import (
    Acknowledgement,
    AckRequest,
    Alarm,
    Assessment,
    AssessmentCurrent,
    AuditLogEntry,
    Error,
    Health,
    Reading,
    ThresholdSet,
)

__all__ = [
    "Source",
    "SensorStatus",
    "RiskLevel",
    "AlarmSeverity",
    "AlarmState",
    "AuditEventType",
    "Reading",
    "Assessment",
    "Alarm",
    "Acknowledgement",
    "ThresholdSet",
    "AuditLogEntry",
    # Wire-Schemas der /v1-API (Contract v1):
    "AssessmentCurrent",
    "Health",
    "Error",
    "AckRequest",
]
