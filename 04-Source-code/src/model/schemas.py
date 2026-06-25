"""Pydantic-Schemas der 6 Domaenen-Entitaeten (DTB-12 / Backend-Konzept §4).

DB-agnostische Naht: diese Modelle definieren Struktur + Validierung; die Persistenz
(rohes PyMySQL, E-35) bildet sie auf das DDL in migrations/schema.sql ab.

UTC-Erzwingung: alle datetime-Felder muessen zeitzonenbewusst sein und werden auf UTC
normalisiert (MySQL DATETIME ist zeitzonenlos -> es wird ausschliesslich UTC gespeichert).
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import (
    AlarmSeverity,
    AlarmState,
    AuditEventType,
    RiskLevel,
    SensorStatus,
    Source,
)


class _Base(BaseModel):
    """Gemeinsame Basis: keine unbekannten Felder, UTC-Erzwingung fuer alle datetime-Felder."""

    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def _enforce_utc(cls, value: object) -> object:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("Zeitstempel muss zeitzonenbewusst sein (UTC erwartet).")
            return value.astimezone(UTC)
        return value


class Reading(_Base):
    """Einzelner Messwert-Snapshot. Sensor-Felder stammen aus G1s GET /current,
    der Rest wird von G2 gesetzt/berechnet."""

    id: int | None = None
    # --- von G1 (GET /current) ---
    sensor_id: str
    measured_at: datetime  # UTC, = G1 measured_at (= ts)
    surface_temp_c: float
    air_temp_c: float
    humidity_pct: float  # Luftfeuchte
    pressure_hpa: float | None = None
    status: SensorStatus = SensorStatus.OK
    # --- von G2 gesetzt/berechnet ---
    received_at: datetime  # UTC, Poll-Zeit
    dew_point_c: float | None = None  # berechnet (Magnus) aus air_temp_c + humidity_pct
    source: Source = Source.REAL


class Assessment(_Base):
    """Ergebnis der Vereisungsbewertung. Speichert die entscheidungsrelevanten Werte
    als Snapshot (audit-fest, auch wenn das Reading per Retention geloescht wird)."""

    id: int | None = None
    ts: datetime  # UTC, Bewertungszeitpunkt
    reading_id: int | None = None
    threshold_set_id: int | None = None
    risk_level: RiskLevel
    driving_factor: str | None = None
    explanation: str | None = None
    # Entscheidungs-Snapshot:
    surface_temp_c: float | None = None
    dew_point_c: float | None = None
    delta_t: float | None = None  # T_s - T_d
    humidity_pct: float | None = None


class Alarm(_Base):
    """Aus einer Bewertung erzeugter Alarm (kein Aktor, RB-01)."""

    id: int | None = None
    assessment_id: int
    severity: AlarmSeverity
    raised_at: datetime
    state: AlarmState = AlarmState.ACTIVE


class Acknowledgement(_Base):
    """Quittierung eines Alarms durch einen Operator (append-only, NF-09)."""

    id: int | None = None
    alarm_id: int
    operator: str
    note: str | None = None
    ts: datetime


class ThresholdSet(_Base):
    """Versionierter Satz parametrierbarer Schwellenwerte (NF-05)."""

    id: int | None = None
    name: str
    params: dict[str, Any]
    valid_from: datetime
    changed_by: str


class AuditLogEntry(_Base):
    """Append-only Eintrag im Audit-/Event-Log (NF-09)."""

    id: int | None = None
    ts: datetime
    event_type: AuditEventType
    entity_type: str = Field(max_length=32)
    entity_id: int | None = None
    actor: str = Field(default="system", max_length=128)
    detail: dict[str, Any] | None = None
