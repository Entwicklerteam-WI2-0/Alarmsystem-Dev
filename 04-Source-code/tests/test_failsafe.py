"""Tests fuer die Fail-safe-Stale-Erkennung (DTB-13).

Stale-Daten und DB-Ausfall sind zwei getrennte Fail-safe-Faelle, die beide
risk_level=unknown produzieren (NF-01/E-34).
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.assessment.failsafe import build_unknown_assessment, is_stale
from src.model.enums import RiskLevel
from src.model.schemas import Reading


@pytest.fixture
def sensor_id() -> str:
    return "anr-rwy-01"


@pytest.fixture
def fresh_reading(sensor_id: str) -> Reading:
    return Reading(
        sensor_id=sensor_id,
        measured_at=datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC),
        surface_temp_c=-0.4,
        air_temp_c=1.2,
        humidity_pct=96.0,
        received_at=datetime(2026, 6, 23, 10, 0, 1, tzinfo=UTC),
    )


def test_is_stale_with_fresh_reading_returns_false(fresh_reading: Reading) -> None:
    now = fresh_reading.measured_at + timedelta(seconds=60)
    assert is_stale(fresh_reading, now, timeout_s=120) is False


def test_is_stale_at_exact_timeout_returns_false(fresh_reading: Reading) -> None:
    # <= timeout gilt noch als frisch (DATETIME(3)-Vergleich konservativ).
    now = fresh_reading.measured_at + timedelta(seconds=120)
    assert is_stale(fresh_reading, now, timeout_s=120) is False


def test_is_stale_with_old_reading_returns_true(fresh_reading: Reading) -> None:
    now = fresh_reading.measured_at + timedelta(seconds=121)
    assert is_stale(fresh_reading, now, timeout_s=120) is True


def test_is_stale_with_none_reading_returns_true() -> None:
    now = datetime.now(UTC)
    assert is_stale(None, now, timeout_s=120) is True


def test_build_unknown_assessment_for_stale_has_correct_values() -> None:
    ts = datetime.now(UTC)
    assessment = build_unknown_assessment(reason="stale data", ts=ts)

    assert assessment.risk_level is RiskLevel.UNKNOWN
    assert assessment.explanation == "Fail-safe: stale data"
    assert assessment.ts == ts


def test_build_unknown_assessment_for_db_error_has_correct_values() -> None:
    ts = datetime.now(UTC)
    assessment = build_unknown_assessment(reason="database unreachable", ts=ts)

    assert assessment.risk_level is RiskLevel.UNKNOWN
    assert assessment.explanation == "Fail-safe: database unreachable"
    assert assessment.ts == ts
