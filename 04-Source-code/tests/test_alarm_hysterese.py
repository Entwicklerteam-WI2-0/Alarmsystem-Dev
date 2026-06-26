"""Tests für die Alarm-Hysterese/Entprellung (DTB-27, Schwellenwerte.md §2).

Eskalation (On-Delay): Ein Alarm wird erst ausgelöst, wenn ORANGE/ROT
mindestens `on_delay_s` Sekunden ununterbrochen anliegt (ISA-18.2 gegen Chattering).
Die Zeit wird explizit übergeben (`jetzt`) — deterministische Tests ohne Uhr-Mock.

RB-01: Die Engine ist reine Entscheidungsunterstützung; sie löst nur aus und
beendet KEINEN aktiven Alarm automatisch (Clearing manuell, FA-10).
"""

from datetime import UTC, datetime, timedelta

from src.alarm.hysterese import AlarmHysterese
from src.config.loader import HystereseParameter
from src.model.enums import AlarmSeverity, RiskLevel

_PARAMS = HystereseParameter(
    on_delay_s=60.0,
    downgrade_stable_s=300.0,
    downgrade_undershoot_c=0.5,
)

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


def _engine() -> AlarmHysterese:
    return AlarmHysterese(_PARAMS)


def test_einzelne_orange_beobachtung_loest_nicht_sofort_aus():
    # Arrange
    engine = _engine()
    # Act — erste alarmwürdige Beobachtung startet nur den On-Delay-Timer.
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0)
    # Assert
    assert ausloesung is None


def test_orange_unter_on_delay_loest_nicht_aus():
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    # 59 s < 60 s On-Delay
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=59))
    assert ausloesung is None


def test_orange_ab_on_delay_loest_warning_aus():
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    # genau 60 s -> Schwelle erreicht (>=)
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=60))
    assert ausloesung is not None
    assert ausloesung.severity is AlarmSeverity.WARNING
    assert ausloesung.ausgeloest_am == _T0 + timedelta(seconds=60)


def test_rot_ab_on_delay_loest_critical_aus():
    engine = _engine()
    engine.beobachte(RiskLevel.RED, _T0)
    ausloesung = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=70))
    assert ausloesung is not None
    assert ausloesung.severity is AlarmSeverity.CRITICAL


def test_gruen_zwischendurch_setzt_on_delay_zurueck():
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    # Bedingung entfällt vor Ablauf -> Timer-Reset
    engine.beobachte(RiskLevel.GREEN, _T0 + timedelta(seconds=30))
    # Neue ORANGE-Phase startet den Timer neu; 40 s nach Neustart < 60 s
    engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=40))
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=80))
    assert ausloesung is None


def test_kein_zweiter_alarm_solange_aktiv():
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    erste = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=60))
    assert erste is not None
    # Weitere ORANGE-Beobachtungen erzeugen keinen erneuten Alarm (bereits aktiv).
    zweite = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=120))
    assert zweite is None


def test_gelb_ist_nicht_alarmwuerdig_und_startet_keinen_timer():
    engine = _engine()
    engine.beobachte(RiskLevel.YELLOW, _T0)
    # 120 s GELB -> kein Alarm (GELB ist Vorwarnung, kein Alarm).
    ausloesung = engine.beobachte(RiskLevel.YELLOW, _T0 + timedelta(seconds=120))
    assert ausloesung is None
