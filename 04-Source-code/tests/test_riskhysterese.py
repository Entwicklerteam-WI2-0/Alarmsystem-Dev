"""Tests für die Anzeige-Hysterese / Rückstufung (DTB-27, Schwellenwerte.md §2).

Hoch/UNKNOWN sofort; runter erst nach 0,5-Deadband (verschobenes Schwellen-Set) +
downgrade_stable_s (300 s) stabil. Default-Schwellen (gefrierpunkt 0, gelb_auffang 1,
kondensation 0, feucht 1; undershoot 0,5; stable 300).
"""

import math
from datetime import UTC, datetime, timedelta

import pytest

from src.alarm.riskhysterese import RiskHysterese
from src.config.loader import load_thresholds
from src.model.enums import RiskLevel

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)
_THR = load_thresholds()  # Default-Schwellen aus config/thresholds.json


def _engine() -> RiskHysterese:
    return RiskHysterese(_THR.hysterese)


def _bewerte(engine, t_s, t_d, jetzt):
    return engine.bewerten(t_s, t_d, _THR, jetzt)


# Referenz-Messwerte je Zielstufe (Default-Schwellen):
#   GRÜN   T_s=2,  T_d=-5   (T_s>1, ΔT=7 nicht feucht)
#   GELB   T_s=0.5,T_d=-5   (0<T_s<=1)
#   ORANGE T_s=-1, T_d=-1.5 (T_s<=0, ΔT=0.5 feucht, ΔT>0)
#   ROT    T_s=-1, T_d=-1   (T_s<=0, ΔT=0)


def test_erstaufruf_uebernimmt_rohstufe():
    engine = _engine()
    assert _bewerte(engine, 0.5, -5.0, _T0) is RiskLevel.YELLOW


def test_hochstufung_sofort():
    engine = _engine()
    _bewerte(engine, 2.0, -5.0, _T0)  # GRÜN
    assert _bewerte(engine, -1.0, -1.0, _T0 + timedelta(seconds=10)) is RiskLevel.RED


def test_unknown_sofort():
    engine = _engine()
    _bewerte(engine, -1.0, -1.0, _T0)  # ROT
    assert _bewerte(engine, math.nan, -1.0, _T0 + timedelta(seconds=10)) is RiskLevel.UNKNOWN


def test_recovery_aus_unknown_sofort():
    engine = _engine()
    _bewerte(engine, -1.0, -1.0, _T0)  # ROT
    _bewerte(engine, math.nan, -1.0, _T0 + timedelta(seconds=10))  # UNKNOWN
    # Aus UNKNOWN heraus die naechste gueltige Stufe sofort uebernehmen (auch "runter").
    assert _bewerte(engine, 2.0, -5.0, _T0 + timedelta(seconds=20)) is RiskLevel.GREEN


def test_herabstufung_im_deadband_haelt():
    engine = _engine()
    _bewerte(engine, 0.5, -5.0, _T0)  # GELB
    # T_s=1.3: roh GRÜN, aber gegen verschobene Schwelle (gelb_auffang 1.5) noch GELB -> halten.
    assert _bewerte(engine, 1.3, -5.0, _T0 + timedelta(seconds=30)) is RiskLevel.YELLOW


def test_herabstufung_deadband_ueberschritten_aber_instabil_haelt():
    engine = _engine()
    _bewerte(engine, 0.5, -5.0, _T0)  # GELB
    _bewerte(engine, 1.6, -5.0, _T0 + timedelta(seconds=10))  # Deadband frei, Timer startet
    # 200 s < downgrade_stable 300 s -> noch GELB.
    assert _bewerte(engine, 1.6, -5.0, _T0 + timedelta(seconds=210)) is RiskLevel.YELLOW


def test_herabstufung_nach_stabilitaet():
    engine = _engine()
    _bewerte(engine, 0.5, -5.0, _T0)  # GELB
    _bewerte(engine, 1.6, -5.0, _T0 + timedelta(seconds=10))  # Timer t0+10
    assert _bewerte(engine, 1.6, -5.0, _T0 + timedelta(seconds=310)) is RiskLevel.GREEN


def test_herabstufung_flicker_setzt_stabilitaet_zurueck():
    engine = _engine()
    _bewerte(engine, 0.5, -5.0, _T0)  # GELB
    _bewerte(engine, 1.6, -5.0, _T0 + timedelta(seconds=10))  # Timer t0+10
    _bewerte(engine, 1.3, -5.0, _T0 + timedelta(seconds=40))  # zurueck ins Deadband -> Reset
    _bewerte(engine, 1.6, -5.0, _T0 + timedelta(seconds=50))  # Timer neu t0+50
    # Timer lief erst ab t0+50 -> bei t0+310 erst 260 s < 300 -> noch GELB.
    assert _bewerte(engine, 1.6, -5.0, _T0 + timedelta(seconds=310)) is RiskLevel.YELLOW
    assert _bewerte(engine, 1.6, -5.0, _T0 + timedelta(seconds=350)) is RiskLevel.GREEN


def test_delta_t_deadband_rot_haelt_dann_orange():
    engine = _engine()
    _bewerte(engine, -1.0, -1.0, _T0)  # ROT (ΔT=0)
    # ΔT=0.4: roh ORANGE, aber gegen verschobene Kondensation (0.5) noch ROT -> halten.
    assert _bewerte(engine, -1.0, -1.4, _T0 + timedelta(seconds=30)) is RiskLevel.RED
    # ΔT=0.6: Deadband frei -> Timer; nach 300 s -> ORANGE.
    _bewerte(engine, -1.0, -1.6, _T0 + timedelta(seconds=40))  # Timer
    assert _bewerte(engine, -1.0, -1.6, _T0 + timedelta(seconds=340)) is RiskLevel.ORANGE


def test_mehrstufiger_abstieg_landet_auf_konservativer_stufe():
    # Mehrstufiger Abstieg darf die Anzeige nicht eine Stufe zu sicher springen lassen:
    # current ROT, Messung T_s=0.3/T_d=-1.0 -> roh GELB, aber gegen das verschobene Set
    # (gefrierpunkt 0.5, feucht 1.5) noch ORANGE. Nach Stabilitaet -> ORANGE (nicht GELB),
    # weil die konservative Lesung erst eine Stufe tiefer erlaubt (NF-01-Geist).
    engine = _engine()
    _bewerte(engine, -1.0, -1.0, _T0)  # ROT
    _bewerte(engine, 0.3, -1.0, _T0 + timedelta(seconds=10))  # Deadband frei -> Timer
    assert _bewerte(engine, 0.3, -1.0, _T0 + timedelta(seconds=310)) is RiskLevel.ORANGE


def test_dauerhaft_im_deadband_haelt_ueber_stabilitaetsdauer():
    # T_s=1.3 liegt dauerhaft im Deadband (roh GRÜN, streng == current GELB). Auch ueber
    # downgrade_stable_s hinaus muss GELB gehalten werden (pinnt `streng >= current`).
    engine = _engine()
    _bewerte(engine, 0.5, -5.0, _T0)  # GELB
    _bewerte(engine, 1.3, -5.0, _T0 + timedelta(seconds=10))
    assert _bewerte(engine, 1.3, -5.0, _T0 + timedelta(seconds=400)) is RiskLevel.YELLOW


def test_naive_datetime_wird_abgewiesen():
    engine = _engine()
    with pytest.raises(ValueError):
        engine.bewerten(0.5, -5.0, _THR, datetime(2026, 6, 26, 12, 0, 0))  # noqa: DTZ001
