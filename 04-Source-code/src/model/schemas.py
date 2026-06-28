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
    # max_length analog zu AssessmentCurrent (Wire-Modell): build_assessment_current
    # reicht diese Felder 1:1 an die Naht weiter -> Speicher- und Wire-Invariante
    # konsistent halten, sonst kann ein zu langer Text erst beim Serven (DTB-43) als
    # ValidationError auffallen (DTB-64+ befuellt explanation/driving_factor).
    driving_factor: str | None = Field(default=None, max_length=64)
    explanation: str | None = Field(default=None, max_length=512)
    # Entscheidungs-Snapshot:
    surface_temp_c: float | None = None
    dew_point_c: float | None = None
    delta_t: float | None = None  # T_s - T_d
    humidity_pct: float | None = None
    # DTB-33 (FA-06/FA-05): 30-min-T_s-Prognose, die diese Bewertung beeinflusst hat.
    # None = keine Prognose verfuegbar/eingegangen. NICHT Teil des G2->G3-Wire-Contracts.
    forecast_surface_temp_c: float | None = None


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


class ReadingResponse(_Base):
    """Wire-Schema fuer GET /v1/readings (DTB-34, Contract v1).

    Spiegelt das interne Reading-Modell, erzwingt aber eine gueltige ID
    (Readings aus der DB haben immer eine id). Trennung internes Modell /
    aussen-Schnittstelle, analog AssessmentCurrent.
    """

    id: int
    sensor_id: str
    measured_at: datetime
    surface_temp_c: float
    air_temp_c: float
    humidity_pct: float
    pressure_hpa: float | None = None
    status: SensorStatus
    received_at: datetime
    dew_point_c: float | None = None
    source: Source


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
    entity_type: str = Field(min_length=1, max_length=32)
    entity_id: int | None = None
    actor: str = Field(default="system", min_length=1, max_length=128)
    detail: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Wire-Schemas der bereitgestellten /v1-API (G2 -> G3, Contract v1, E-36).
# Eigene Modelle statt der DB-Entitaeten: die Naht nach aussen ist flach und
# stabil; sie darf sich unabhaengig vom internen Datenmodell entwickeln.
# ---------------------------------------------------------------------------


class AssessmentCurrent(_Base):
    """Flacher G2->G3-Response fuer GET /v1/assessment/current (kein Envelope, E-36).

    Ampel + Roh-Messwerte. Fail-safe-Invarianten (NF-01) garantiert die
    Serving-Schicht (build_assessment_current), NICHT dieses Schema:
    `green` nur bei `is_stale=false` UND `sensor_status=ok`; bei Stale ODER
    Fault -> `unknown`; genullte Messwerte treten nur bei `unknown` auf.
    """

    risk_level: RiskLevel
    driving_factor: str | None = Field(default=None, max_length=64)
    explanation: str | None = Field(default=None, max_length=512)
    surface_temp_c: float | None = None
    dew_point_c: float | None = None
    delta_t: float | None = None
    humidity_pct: float | None = None
    measured_at: datetime  # G1-Messzeit; auf 200 immer gesetzt
    assessed_at: datetime  # G2-Bewertungszeit
    is_stale: bool
    sensor_status: SensorStatus


class Health(_Base):
    """Liveness-Response fuer GET /v1/health (Contract v1)."""

    # min_length/max_length analog zu Error.code/message (konsistente Wire-Schemas);
    # der 503-Pfad wird ueber den HTTP-Status signalisiert, nicht ueber status.
    status: str = Field(default="ok", min_length=1, max_length=16)


class Error(_Base):
    """Maschinenlesbares Fehlerformat (Contract v1): keine internen Details/Secrets."""

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=512)


class AckRequest(_Base):
    """Request-Body fuer POST /v1/alarms/{id}/ack (Contract v1, NF-09)."""

    operator: str = Field(min_length=1, max_length=128)
    note: str | None = Field(default=None, max_length=512)


class ThresholdUpdateRequest(_Base):
    """Request-Body fuer POST /v1/thresholds (DTB-63, NF-07).

    `thresholds` ist die vollstaendige Schwellen-Struktur (wie GET /v1/thresholds sie
    liefert); fachlich validiert wird sie im Endpoint ueber den kanonischen Loader
    (`parse_thresholds`) -> bei ungueltigen Werten 422. `changed_by` ist der
    selbstdeklarierte Operator fuer den Audit-Trail (NF-09/K6): bei einem geteilten
    API-Key der einzige Accountability-Anker (analog `operator` bei der Quittierung).
    `name` ist ein Label fuer den versionierten Schwellensatz (threshold_set.name).
    """

    changed_by: str = Field(min_length=1, max_length=128)
    name: str = Field(default="manuelle Aktualisierung", min_length=1, max_length=128)
    # max_length = Obergrenze der Top-Level-Sektionen (OpenAPI maxProperties): die gueltige
    # Struktur hat 6 (parse_thresholds), 64 laesst Spielraum fuer optionale Kommentar-Keys.
    # Bremst pathologisch breite Payloads bereits am Schema, bevor parse_thresholds ueber
    # alle Keys iteriert. Ein echtes Byte-Groessen-Limit gehoert an Server/Proxy
    # (Request-Body-Limit), nicht ins Schema -- dies bindet nur die Schluessel-Anzahl.
    thresholds: dict[str, Any] = Field(max_length=64)
