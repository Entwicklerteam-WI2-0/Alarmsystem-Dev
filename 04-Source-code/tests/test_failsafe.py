"""Tests fuer die Fail-safe-Stale-Erkennung und Plausibilitaet (DTB-13).

Stale-Daten, DB-Ausfall und unplausible Werte sind getrennte Fail-safe-Faelle,
die alle risk_level=unknown produzieren (NF-01/E-34).
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.assessment.failsafe import build_unknown_assessment, check_plausibility, is_stale
from src.config.loader import DatenqualitaetSchwellen
from src.model.enums import RiskLevel
from src.model.schemas import Reading


@pytest.fixture
def sensor_id() -> str:
    return "anr-rwy-01"


@pytest.fixture
def quality_thresholds() -> DatenqualitaetSchwellen:
    return DatenqualitaetSchwellen(
        stale_timeout_s=120.0,
        max_temp_jump_c_per_min=5.0,
        flatline_timeout_min=15.0,
        flatline_epsilon_c=0.15,
        max_clock_skew_s=5.0,
        min_plausible_dew_point_c=-50.0,
    )


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


def _build_previous(
    fresh_reading: Reading,
    minutes_ago: float,
    surface_temp_c: float,
) -> Reading:
    return Reading(
        sensor_id=fresh_reading.sensor_id,
        measured_at=fresh_reading.measured_at - timedelta(minutes=minutes_ago),
        surface_temp_c=surface_temp_c,
        air_temp_c=fresh_reading.air_temp_c,
        humidity_pct=fresh_reading.humidity_pct,
        received_at=fresh_reading.received_at - timedelta(minutes=minutes_ago),
    )


# ---------------------------------------------------------------------------
# Stale
# ---------------------------------------------------------------------------
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


def test_is_stale_with_naive_now_raises(fresh_reading: Reading) -> None:
    # Naive now-Werte muessen frueh erkannt werden, bevor is_stale in DTB-38
    # verdrahtet wird -> sonst TypeError-Crash im Assessment-Loop.
    naive_now = datetime(2026, 6, 23, 10, 2, 0)
    with pytest.raises(ValueError, match="zeitzonenbewusst"):
        is_stale(fresh_reading, naive_now, timeout_s=120)


def test_is_stale_with_none_reading_and_naive_now_raises() -> None:
    # now wird VOR dem reading-None-Check validiert: ein naiver now-Wert faellt auch
    # dann auf, wenn (noch) kein Reading vorliegt -> in einer Multi-Sensor-Schleife
    # bleibt der Fehler nicht bis zum naechsten Sensor verborgen (DTB-93 LOW).
    naive_now = datetime(2026, 6, 23, 10, 2, 0)
    with pytest.raises(ValueError, match="zeitzonenbewusst"):
        is_stale(None, naive_now, timeout_s=120)


@pytest.mark.parametrize("bad_timeout", [0, -1, -0.5])
def test_is_stale_with_non_positive_timeout_raises(
    fresh_reading: Reading, bad_timeout: float
) -> None:
    now = fresh_reading.measured_at + timedelta(seconds=60)
    with pytest.raises(ValueError, match="timeout_s muss positiv sein"):
        is_stale(fresh_reading, now, timeout_s=bad_timeout)


def test_check_plausibility_no_previous_returns_none(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    assert check_plausibility(fresh_reading, None, quality_thresholds) is None


def test_check_plausibility_negative_timestamp_order_is_unplausible(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    previous = _build_previous(fresh_reading, minutes_ago=-1.0, surface_temp_c=-0.4)
    reason = check_plausibility(fresh_reading, previous, quality_thresholds)
    assert reason == "invalid timestamp order"


def test_check_plausibility_normal_change_is_plausible(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    previous = _build_previous(fresh_reading, minutes_ago=1.0, surface_temp_c=-0.5)
    assert check_plausibility(fresh_reading, previous, quality_thresholds) is None


def test_check_plausibility_jump_exceeding_limit_is_unplausible(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    # 6 C in 1 min -> 6 C/min > 5 C/min
    previous = _build_previous(fresh_reading, minutes_ago=1.0, surface_temp_c=-6.4)
    reason = check_plausibility(fresh_reading, previous, quality_thresholds)
    assert reason is not None
    assert "jump" in reason


def test_check_plausibility_jump_at_exact_limit_is_plausible(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    # 5 C in 1 min -> genau 5 C/min -> noch innerhalb Limit.
    previous = _build_previous(fresh_reading, minutes_ago=1.0, surface_temp_c=-5.4)
    assert check_plausibility(fresh_reading, previous, quality_thresholds) is None


def test_check_plausibility_sub_second_interval_is_plausible(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    # Sub-Sekunden-Intervalle duerfen nicht zu einer Division durch fast-0 fuehren
    # und falsch als Sprung gewertet werden (LOW aus Review).
    previous = Reading(
        sensor_id=fresh_reading.sensor_id,
        measured_at=fresh_reading.measured_at - timedelta(milliseconds=500),
        surface_temp_c=fresh_reading.surface_temp_c - 10.0,
        air_temp_c=fresh_reading.air_temp_c,
        humidity_pct=fresh_reading.humidity_pct,
        received_at=fresh_reading.received_at - timedelta(milliseconds=500),
    )
    assert check_plausibility(fresh_reading, previous, quality_thresholds) is None


def test_check_plausibility_cross_sensor_raises(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    previous = _build_previous(fresh_reading, minutes_ago=1.0, surface_temp_c=-0.5)
    previous = previous.model_copy(update={"sensor_id": "anr-rwy-02"})
    # ValueError statt assert, damit der Guard auch unter python -O erhalten bleibt.
    with pytest.raises(ValueError, match="denselben Sensor"):
        check_plausibility(fresh_reading, previous, quality_thresholds)


# ---------------------------------------------------------------------------
# Plausibilitaet - Flatline
# ---------------------------------------------------------------------------
def test_check_plausibility_flatline_exceeding_timeout_is_unplausible(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    previous = _build_previous(fresh_reading, minutes_ago=15.0, surface_temp_c=-0.4)
    reason = check_plausibility(fresh_reading, previous, quality_thresholds)
    assert reason == "temperature flatline"


def test_check_plausibility_change_within_flatline_window_is_plausible(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    # 15 min auseinander, aber deutliche Aenderung -> kein Flatline.
    previous = _build_previous(fresh_reading, minutes_ago=15.0, surface_temp_c=-1.0)
    assert check_plausibility(fresh_reading, previous, quality_thresholds) is None


def test_check_plausibility_small_change_before_flatline_timeout_is_plausible(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    # 14 min auseinander, keine Aenderung -> noch unter dem Timeout.
    previous = _build_previous(fresh_reading, minutes_ago=14.0, surface_temp_c=-0.4)
    assert check_plausibility(fresh_reading, previous, quality_thresholds) is None


# ---------------------------------------------------------------------------
# Assessment-Builder
# ---------------------------------------------------------------------------
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


def test_build_unknown_assessment_for_plausibility_has_correct_values() -> None:
    ts = datetime.now(UTC)
    assessment = build_unknown_assessment(reason="temperature jump", ts=ts)

    assert assessment.risk_level is RiskLevel.UNKNOWN
    assert assessment.explanation == "Fail-safe: temperature jump"
    assert assessment.ts == ts


def test_build_unknown_assessment_sanitizes_newlines() -> None:
    ts = datetime.now(UTC)
    assessment = build_unknown_assessment(reason="line1\nline2", ts=ts)

    assert "\n" not in assessment.explanation
    assert "line1 line2" in assessment.explanation


def test_build_unknown_assessment_sanitizes_unicode_line_separators() -> None:
    ts = datetime.now(UTC)
    assessment = build_unknown_assessment(reason="foo\u2028bar\u2029baz", ts=ts)

    assert "\u2028" not in assessment.explanation
    assert "\u2029" not in assessment.explanation
    # Unicode-Zeilentrenner werden wie \n/\r durch Leerzeichen ersetzt, damit
    # Worte nicht zusammenwachsen (DTB-93 LOW).
    assert "foo bar baz" in assessment.explanation


def test_build_unknown_assessment_removes_control_characters() -> None:
    ts = datetime.now(UTC)
    # Control Characters (Unicode-Kategorie Cc, z. B. BEL \x07 und DEL \x7f) werden
    # ersatzlos entfernt (kein Leerzeichen) -> sichert frozenset({"Cc"}) nach DTB-93 LOW ab.
    assessment = build_unknown_assessment(reason="foo\x07bar\x7fbaz", ts=ts)

    assert "\x07" not in assessment.explanation
    assert "\x7f" not in assessment.explanation
    assert "foobarbaz" in assessment.explanation


def test_build_unknown_assessment_truncates_long_reason() -> None:
    ts = datetime.now(UTC)
    max_reason_len = 256
    long_reason = "x" * (max_reason_len + 50)
    assessment = build_unknown_assessment(reason=long_reason, ts=ts)

    assert len(assessment.explanation) <= max_reason_len + len("Fail-safe: ")
    assert assessment.explanation.endswith("...")


def test_check_plausibility_lsb_dither_is_flatline(
    fresh_reading: Reading,
    quality_thresholds: DatenqualitaetSchwellen,
) -> None:
    # Regression DTB-20: ein eingefrorener DS18B20 dithert um 1 LSB (0.0625 C @ 12-Bit).
    # Mit dem alten epsilon=0.01 entkam das der Erkennung; mit 0.15 muss es Flatline sein.
    dither_c = 0.0625
    assert dither_c < quality_thresholds.flatline_epsilon_c
    previous = _build_previous(
        fresh_reading,
        minutes_ago=15.0,
        surface_temp_c=fresh_reading.surface_temp_c - dither_c,
    )
    reason = check_plausibility(fresh_reading, previous, quality_thresholds)
    assert reason == "temperature flatline"
