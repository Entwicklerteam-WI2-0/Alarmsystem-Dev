"""Tests fuer die displayed_risk_level-Persistenz (DTB-27 Hysterese-Feld).

Stellt sicher, dass das neue Feld save -> get_latest ueberlebt (InMemory-Double).
Die echte MySQL-Roundtrip-Persistenz wird in test_assessment_repository_integration.py
gegen die DB geprueft; hier die InMemory-Naht als schnelle Regression.
"""

from datetime import UTC, datetime

from src.alarm.riskhysterese import RiskHysterese
from src.assessment.service import AssessmentService
from src.config.loader import load_thresholds
from src.model.enums import RiskLevel, SensorStatus
from src.model.schemas import Reading
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository

_THR = load_thresholds()
_T0 = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _reading(now, surface, dew, status=SensorStatus.OK):
    return Reading(
        id=1,
        sensor_id="anr-rwy-01",
        measured_at=now,
        surface_temp_c=surface,
        air_temp_c=3.0,
        humidity_pct=80.0,
        received_at=now,
        dew_point_c=dew,
        status=status,
    )


def test_displayed_risk_level_ueberlebt_inmemory_roundtrip():
    """displayed_risk_level wird persistiert und ist nach get_latest wieder da."""
    arepo = InMemoryAssessmentRepository()
    service = AssessmentService(
        _THR, RiskHysterese(_THR.hysterese), arepo, InMemoryAuditRepository()
    )

    # ORANGE: T_s=-1, T_d=-1.5 -> delta_t=0.5 (feucht)
    result = service.assess_reading(_reading(_T0, surface=-1.0, dew=-1.5), _T0)

    assert result.displayed_risk_level is RiskLevel.ORANGE
    persisted = arepo.get_latest()
    assert persisted is not None
    assert persisted.displayed_risk_level is RiskLevel.ORANGE


def test_displayed_risk_level_unknown_in_failsafe_wird_persistiert():
    """Fail-safe (fault) setzt displayed=UNKNOWN, und das wird auch persistiert."""
    arepo = InMemoryAssessmentRepository()
    service = AssessmentService(
        _THR, RiskHysterese(_THR.hysterese), arepo, InMemoryAuditRepository()
    )

    result = service.assess_reading(
        _reading(_T0, surface=-1.0, dew=-1.0, status=SensorStatus.FAULT), _T0
    )

    assert result.displayed_risk_level is RiskLevel.UNKNOWN
    persisted = arepo.get_latest()
    assert persisted is not None
    assert persisted.displayed_risk_level is RiskLevel.UNKNOWN
