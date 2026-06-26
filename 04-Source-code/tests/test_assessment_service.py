"""Tests fuer die Assessment-Orchestrierung (DTB-64).

Belegt das **NF-01-Enforcement zur Laufzeit** an beiden Stellen:
- Assess-Zeit (AssessmentService.assess_reading): keine/stale/fault Daten -> unknown,
  nie GRUEN; sonst regulaere Bewertung; Persistenz + Audit verdrahtet.
- Serve-Zeit (build_assessment_current): stale/fault zum Abfragezeitpunkt -> unknown
  + Messwerte genullt; Contract-konformer Wire-Response.

Alle Schwellen aus der Default-Config (DTB-15), keine Hardcodes.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.assessment.service import AssessmentService, build_assessment_current
from src.config.loader import load_thresholds
from src.model.enums import AuditEventType, RiskLevel, SensorStatus
from src.model.schemas import Assessment, Reading
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository
from src.storage.repository import RepositoryError


@pytest.fixture
def thresholds():
    return load_thresholds()


def _reading(
    measured_at: datetime,
    *,
    surface: float = 2.0,
    dew: float | None = 0.0,
    status: SensorStatus = SensorStatus.OK,
    rid: int | None = 1,
) -> Reading:
    """Baut ein Reading; received_at = measured_at (fuer den Test irrelevant).

    `rid` ist defaultmaessig gesetzt (= vom Poller persistiert, DTB-28-Invariante);
    `rid=None` modelliert ein noch nicht persistiertes Reading.
    """
    return Reading(
        id=rid,
        sensor_id="anr-rwy-01",
        measured_at=measured_at,
        surface_temp_c=surface,
        air_temp_c=3.0,
        humidity_pct=80.0,
        received_at=measured_at,
        dew_point_c=dew,
        status=status,
    )


def _make_service(thresholds) -> AssessmentService:
    """Service mit frischen In-Memory-Repos (fuer Tests ohne Repo-Inspektion)."""
    return AssessmentService(
        thresholds, InMemoryAssessmentRepository(), InMemoryAuditRepository()
    )


# ---------------------------------------------------------------------------
# AssessmentService.assess_reading — Assess-Zeit-NF-01 + Persistenz + Audit
# ---------------------------------------------------------------------------


def test_healthy_reading_is_assessed_persisted_and_audited(thresholds):
    # Arrange
    arepo, audit = InMemoryAssessmentRepository(), InMemoryAuditRepository()
    service = AssessmentService(thresholds, arepo, audit)
    now = datetime.now(UTC)

    # Act — T_s=2.0 (>1.0), Taupunkt 0 -> trocken -> GRUEN
    result = service.assess_reading(_reading(now, surface=2.0, dew=0.0), now)

    # Assert
    assert result.risk_level == RiskLevel.GREEN
    assert result.id == 1
    assert arepo.get_latest() is not None
    assert arepo.get_latest().id == 1
    assert len(audit.all()) == 1
    assert audit.all()[0].event_type == AuditEventType.ASSESSMENT_MADE


def test_negative_delta_t_assesses_ice_risk_not_green(thresholds):
    # Arrange — Taupunkt (1.0) UEBER Oberflaechentemp (-0.5): delta_t = -1.5
    # (T_d > T_s) ist ein klares Eisrisiko und muss sicherheitskritisch bewertet
    # werden, nicht GRUEN. Deckt den Service-Pfad fuer einen nicht-gruenen,
    # persistierten Risk-Level ab (assess_ice_risk-Kern, Schwellenwerte.md §2:
    # T_s<=Gefrierpunkt UND delta_t<=Kondensation -> ROT).
    arepo, audit = InMemoryAssessmentRepository(), InMemoryAuditRepository()
    service = AssessmentService(thresholds, arepo, audit)
    now = datetime.now(UTC)

    # Act — T_s=-0.5 (<=Gefrierpunkt 0.0) UND delta_t=-1.5 (<=Kondensation 0.0) -> ROT
    result = service.assess_reading(_reading(now, surface=-0.5, dew=1.0), now)

    # Assert — hoechste Risikostufe ROT, korrekt persistiert + auditiert; nie GRUEN.
    assert result.risk_level == RiskLevel.RED
    assert result.risk_level != RiskLevel.GREEN
    assert result.delta_t == pytest.approx(-1.5)
    assert result.id == 1
    assert arepo.get_latest().id == 1
    assert len(audit.all()) == 1
    assert audit.all()[0].event_type == AuditEventType.ASSESSMENT_MADE


def test_none_reading_is_unknown(thresholds):
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(None, now)

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id is None  # ohne Reading kein Bezug moeglich


def test_fault_reading_is_unknown_never_green(thresholds):
    # Arrange — Werte, die fresh GRUEN ergaeben; fault muss sie ueberstimmen.
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(
        _reading(now, surface=20.0, dew=0.0, status=SensorStatus.FAULT), now
    )

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id == 1  # ausloesendes Reading verknuepft (Traceability)


def test_stale_reading_is_unknown_never_green(thresholds):
    # Arrange — warmes (waere GRUEN) aber veraltetes Reading.
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)

    result = service.assess_reading(_reading(old, surface=20.0, dew=0.0), now)

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id == 1  # ausloesendes Reading verknuepft (Traceability)


def test_naive_now_raises(thresholds):
    service = _make_service(thresholds)

    with pytest.raises(ValueError, match="zeitzonenbewusst"):
        service.assess_reading(None, datetime.now())  # noqa: DTZ005 - bewusst naiv


def test_good_path_requires_persisted_reading_id(thresholds):
    # Arrange — gesundes Reading (waere GRUEN), aber noch nicht persistiert (id=None).
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    # Act + Assert — die DTB-28-Invariante muss laut scheitern, statt einen Snapshot
    # mit reading_id=NULL zu schreiben und so die Audit-Traceability (NF-05) zu brechen.
    with pytest.raises(ValueError, match="Poller muss das Reading"):
        service.assess_reading(_reading(now, surface=2.0, dew=0.0, rid=None), now)


class _ThrowingAuditRepository(InMemoryAuditRepository):
    """Audit-Double, das bei jedem append wirft (best-effort-Garantie testen)."""

    def append(self, entry):  # noqa: ARG002 - Signatur des Interface, Wert ungenutzt
        raise RepositoryError("Audit-Backend nicht verfuegbar")


def test_audit_failure_does_not_break_cycle(thresholds):
    # Arrange — Audit wirft IMMER; der Bewertungszyklus muss trotzdem durchlaufen
    # (NF-01 vor NF-09: ein Audit-Fehler darf den Sicherheits-Output nie blockieren).
    arepo = InMemoryAssessmentRepository()
    service = AssessmentService(thresholds, arepo, _ThrowingAuditRepository())
    now = datetime.now(UTC)

    # Act — gesunder Wert (waere GRUEN); kein raise trotz Audit-Fehler erwartet.
    result = service.assess_reading(_reading(now, surface=2.0, dew=0.0), now)

    # Assert — Bewertung wurde erzeugt UND persistiert, obwohl das Audit scheiterte.
    assert result.id == 1
    assert result.risk_level == RiskLevel.GREEN
    assert arepo.get_latest() is not None


# ---------------------------------------------------------------------------
# build_assessment_current — Serve-Zeit-NF-01 (Wire-Response)
# ---------------------------------------------------------------------------


def test_current_fresh_ok_keeps_assessment(thresholds):
    now = datetime.now(UTC)
    reading = _reading(now, surface=2.0, dew=0.0)
    assessment = Assessment(
        ts=now,
        risk_level=RiskLevel.GREEN,
        surface_temp_c=2.0,
        dew_point_c=0.0,
        delta_t=2.0,
        humidity_pct=80.0,
    )

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level == RiskLevel.GREEN
    assert cur.is_stale is False
    assert cur.sensor_status == SensorStatus.OK
    assert cur.surface_temp_c == 2.0
    assert cur.measured_at == reading.measured_at
    assert cur.assessed_at == assessment.ts


def test_current_stale_forces_unknown_and_nulls_measurements(thresholds):
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)
    reading = _reading(old, surface=2.0, dew=0.0)
    assessment = Assessment(ts=old, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level == RiskLevel.UNKNOWN
    assert cur.is_stale is True
    assert cur.surface_temp_c is None
    assert cur.dew_point_c is None


def test_current_fault_forces_unknown(thresholds):
    now = datetime.now(UTC)
    reading = _reading(now, status=SensorStatus.FAULT)
    assessment = Assessment(ts=now, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level == RiskLevel.UNKNOWN
    assert cur.sensor_status == SensorStatus.FAULT
    assert cur.is_stale is False


def test_current_stale_and_fault_names_both_reasons(thresholds):
    # Arrange — Reading ist gleichzeitig stale UND fault (kombinierter Fail-safe-Pfad).
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)
    reading = _reading(old, status=SensorStatus.FAULT)
    assessment = Assessment(ts=old, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    # Beide Gruende erscheinen in explanation; Invariante bleibt unknown (nie GRUEN).
    assert cur.risk_level == RiskLevel.UNKNOWN
    assert cur.is_stale is True
    assert cur.sensor_status == SensorStatus.FAULT
    assert cur.explanation == "Fail-safe: stale + sensor fault"
