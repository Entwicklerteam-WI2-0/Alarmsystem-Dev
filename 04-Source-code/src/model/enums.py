"""Enums des Datenmodells (DTB-12 / Backend-Konzept §4).

Feste Wertelisten statt freiem Text -> verhindert Tippfehler/Wildwuchs in DB und API.
Die DB spiegelt diese Werte als VARCHAR + CHECK-Constraint (s. migrations/schema.sql).
"""

from enum import StrEnum


class Source(StrEnum):
    """Herkunft eines Messwerts: echter Sensor vs. Simulator (E-09)."""

    REAL = "real"
    SIM = "sim"


class SensorStatus(StrEnum):
    """Sensor-/Lieferstatus aus G1s GET /current `status`."""

    OK = "ok"
    FAULT = "fault"


class RiskLevel(StrEnum):
    """Vereisungs-Risikostufe (Schwellenwerte.md §2).

    UNKNOWN ist der Fail-safe-Zustand (NF-01): bei veralteten/fehlenden Daten
    nie GRUEN -> UNKNOWN statt einer Risikostufe. Gesetzt, aber bewusst noch
    nachzuiterieren (Darstellung gegenueber G3, DTB-19).
    """

    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"
    UNKNOWN = "unknown"


class AlarmSeverity(StrEnum):
    """Schweregrad eines Alarms (abgeleitet aus der ausloesenden Risikostufe)."""

    WARNING = "warning"
    CRITICAL = "critical"


class AlarmState(StrEnum):
    """Lebenszyklus eines Alarms. Quittieren ist reine UI-/Audit-Aktion (RB-01)."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"


class AuditEventType(StrEnum):
    """Ereignistypen im append-only Audit-Log (NF-09)."""

    READING_INGESTED = "reading_ingested"
    ASSESSMENT_MADE = "assessment_made"
    ALARM_RAISED = "alarm_raised"
    ALARM_ACKNOWLEDGED = "alarm_acknowledged"
    THRESHOLD_CHANGED = "threshold_changed"
    SENSOR_FAULT = "sensor_fault"
