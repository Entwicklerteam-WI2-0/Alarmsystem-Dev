"""Enums des Datenmodells (DTB-12 / Backend-Konzept §4).

Feste Wertelisten statt freiem Text -> verhindert Tippfehler/Wildwuchs in DB und API.
Die DB spiegelt diese Werte als VARCHAR + CHECK-Constraint (s. migrations/schema.sql).
"""

from enum import Enum


class Source(str, Enum):
    """Herkunft eines Messwerts: echter Sensor vs. Simulator (E-09)."""

    REAL = "real"
    SIM = "sim"


class SensorStatus(str, Enum):
    """Sensor-/Lieferstatus aus G1s GET /current `status`."""

    OK = "ok"
    FAULT = "fault"


class RiskLevel(str, Enum):
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


class AlarmSeverity(str, Enum):
    """Schweregrad eines Alarms (abgeleitet aus der ausloesenden Risikostufe)."""

    WARNING = "warning"
    CRITICAL = "critical"


class AlarmState(str, Enum):
    """Lebenszyklus eines Alarms. Quittieren ist reine UI-/Audit-Aktion (RB-01)."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"


class AuditEventType(str, Enum):
    """Ereignistypen im append-only Audit-Log (NF-09)."""

    READING_INGESTED = "reading_ingested"
    ASSESSMENT_MADE = "assessment_made"
    ALARM_RAISED = "alarm_raised"
    ALARM_ACKNOWLEDGED = "alarm_acknowledged"
    THRESHOLD_CHANGED = "threshold_changed"
    SENSOR_FAULT = "sensor_fault"
