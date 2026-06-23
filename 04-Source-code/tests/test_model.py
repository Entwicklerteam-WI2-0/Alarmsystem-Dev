"""Tests fuer die Datenmodell-Schemas (DTB-12).

Prueft: UTC-Erzwingung (zeitzonenbewusst), Enum-Validierung, Fail-safe-Stufe UNKNOWN.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.model.enums import AlarmSeverity, AlarmState, RiskLevel, SensorStatus, Source
from src.model.schemas import Alarm, Assessment, Reading

UTC_NOW = datetime(2026, 6, 22, 14, 3, 5, tzinfo=UTC)


def _reading(**overrides):
    base = dict(
        sensor_id="anr-rwy-01",
        measured_at=UTC_NOW,
        received_at=UTC_NOW,
        surface_temp_c=-0.4,
        air_temp_c=1.2,
        humidity_pct=96.0,
        pressure_hpa=1013.0,
    )
    base.update(overrides)
    return Reading(**base)


def test_reading_accepts_tz_aware_and_defaults():
    r = _reading()
    assert r.measured_at.tzinfo == UTC
    assert r.source is Source.REAL
    assert r.status is SensorStatus.OK


def test_reading_normalizes_offset_to_utc():
    plus_two = datetime(2026, 6, 22, 16, 3, 5, tzinfo=timezone(timedelta(hours=2)))
    r = _reading(measured_at=plus_two)
    assert r.measured_at == UTC_NOW


def test_reading_rejects_naive_datetime():
    with pytest.raises(ValidationError):
        _reading(measured_at=datetime(2026, 6, 22, 14, 0, 0))


def test_reading_rejects_unknown_source_enum():
    with pytest.raises(ValidationError):
        _reading(source="bogus")


def test_reading_forbids_extra_fields():
    with pytest.raises(ValidationError):
        _reading(ice_indicator=True)


def test_assessment_unknown_is_valid_failsafe_level():
    a = Assessment(ts=UTC_NOW, risk_level=RiskLevel.UNKNOWN)
    assert a.risk_level is RiskLevel.UNKNOWN


def test_risklevel_values_are_locked():
    assert {level.value for level in RiskLevel} == {
        "green",
        "yellow",
        "orange",
        "red",
        "unknown",
    }


def test_alarm_enums():
    al = Alarm(assessment_id=1, severity=AlarmSeverity.CRITICAL, raised_at=UTC_NOW)
    assert al.state is AlarmState.ACTIVE
    with pytest.raises(ValidationError):
        Alarm(assessment_id=1, severity="fatal", raised_at=UTC_NOW)
