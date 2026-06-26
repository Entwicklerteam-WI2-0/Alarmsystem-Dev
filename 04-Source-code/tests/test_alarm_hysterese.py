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
    max_continuity_gap_s=120.0,
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


# --- Schritt 4: Quittierung (Re-Arming, RB-01) + Severity-Upgrade ---


def _aktiver_warning(engine: AlarmHysterese, start: datetime) -> None:
    """Hilfsroutine: bringt die Engine in den Zustand 'aktiver warning-Alarm'."""
    engine.beobachte(RiskLevel.ORANGE, start)
    ausloesung = engine.beobachte(RiskLevel.ORANGE, start + timedelta(seconds=60))
    assert ausloesung is not None and ausloesung.severity is AlarmSeverity.WARNING


def test_quittierung_armt_engine_fuer_neuen_alarm_neu():
    engine = _engine()
    _aktiver_warning(engine, _T0)
    # Mensch beendet den Alarm (manuell, RB-01/FA-10) -> Engine wieder auslösebereit.
    engine.quittiert()
    # Neue ORANGE-Phase muss erneut einen Alarm auslösen können.
    engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=600))
    erneut = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=660))
    assert erneut is not None
    assert erneut.severity is AlarmSeverity.WARNING


def test_quittierung_ohne_aktiven_alarm_ist_unkritisch():
    engine = _engine()
    # Darf nicht crashen und ändert nichts am Normalverhalten.
    engine.quittiert()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=60))
    assert ausloesung is not None


def test_upgrade_warning_zu_critical_nach_on_delay():
    engine = _engine()
    _aktiver_warning(engine, _T0)
    # ROT liegt nun an: Upgrade ist eine Hochstufung -> ebenfalls On-Delay.
    engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=70))
    upgrade = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=130))
    assert upgrade is not None
    assert upgrade.severity is AlarmSeverity.CRITICAL


def test_upgrade_unter_on_delay_loest_nicht_aus():
    engine = _engine()
    _aktiver_warning(engine, _T0)
    engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=70))
    # 30 s ROT < On-Delay -> noch kein Upgrade.
    upgrade = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=100))
    assert upgrade is None


def test_kein_zweiter_critical_nach_upgrade():
    engine = _engine()
    _aktiver_warning(engine, _T0)
    engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=70))
    erstes = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=130))
    assert erstes is not None
    # Weiter ROT -> kein erneutes critical-Event (bereits auf höchster Stufe).
    weiteres = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=300))
    assert weiteres is None


def test_kein_auto_downgrade_critical_bleibt_sticky():
    engine = _engine()
    # critical aktiv machen
    engine.beobachte(RiskLevel.RED, _T0)
    aktiv = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=60))
    assert aktiv is not None and aktiv.severity is AlarmSeverity.CRITICAL
    # Risiko sinkt: KEIN automatisches Downgrade/Clear (RB-01) -> keine Events.
    assert engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=400)) is None
    assert engine.beobachte(RiskLevel.GREEN, _T0 + timedelta(seconds=800)) is None


# --- Review-Runde 1: Fail-safe-Härtung (UNKNOWN-Freeze, Max-Severity, tz, quittiert) ---


def test_naive_datetime_wird_abgewiesen():
    engine = _engine()
    # Contract §2a D: alle Zeitstempel UTC/tz-aware. Naive Zeit -> laut scheitern,
    # nicht im Alarmpfad mit TypeError crashen (Under-Alarm).
    import pytest

    with pytest.raises(ValueError):
        engine.beobachte(RiskLevel.ORANGE, datetime(2026, 6, 26, 12, 0, 0))  # noqa: DTZ001


def test_unknown_friert_on_delay_ein_statt_zu_resetten():
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    # UNKNOWN = Unsicherheit/Stale -> darf die laufende Eskalation NICHT zuruecksetzen.
    engine.beobachte(RiskLevel.UNKNOWN, _T0 + timedelta(seconds=30))
    # Trotz UNKNOWN-Blip: 70 s nach Start liegt wieder ORANGE an -> Alarm muss feuern.
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=70))
    assert ausloesung is not None
    assert ausloesung.severity is AlarmSeverity.WARNING


def test_oszillation_orange_unknown_loest_trotzdem_aus():
    # Defekter Vorfeld-Sensor (R1/R2): ORANGE <-> UNKNOWN flackert poll-weise.
    # Der reale Vereisungsalarm darf NICHT dauerhaft unterdrueckt werden (NF-01/K1).
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    engine.beobachte(RiskLevel.UNKNOWN, _T0 + timedelta(seconds=20))
    engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=40))
    engine.beobachte(RiskLevel.UNKNOWN, _T0 + timedelta(seconds=55))
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=65))
    assert ausloesung is not None


def test_unknown_allein_loest_keinen_alarm_aus():
    engine = _engine()
    engine.beobachte(RiskLevel.UNKNOWN, _T0)
    # 120 s reines UNKNOWN -> kein Alarm (Unsicherheit ist kein ORANGE/ROT).
    ausloesung = engine.beobachte(RiskLevel.UNKNOWN, _T0 + timedelta(seconds=120))
    assert ausloesung is None


def test_transientes_rot_im_pending_loest_critical_aus():
    # ROT zu Beginn der Eskalation, danach ORANGE: die hoechste Stufe der Phase
    # darf nicht verloren gehen -> Alarm feuert CRITICAL (Safety-Bias).
    engine = _engine()
    engine.beobachte(RiskLevel.RED, _T0)
    engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=30))
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=60))
    assert ausloesung is not None
    assert ausloesung.severity is AlarmSeverity.CRITICAL


def test_rot_innerhalb_pending_hebt_severity_auf_critical():
    # ORANGE startet die Eskalation, ROT eskaliert sie INNERHALB des Fensters:
    # die gefeuerte Stufe muss die hoechste der Phase sein (critical), nicht warning.
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=30))
    ausloesung = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=60))
    assert ausloesung is not None
    assert ausloesung.severity is AlarmSeverity.CRITICAL


def test_quittiert_ohne_aktiven_alarm_unterbricht_eskalation_nicht():
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)  # Eskalation laeuft, noch kein aktiver Alarm
    engine.quittiert()  # Fehlbedienung ohne aktiven Alarm -> darf Pending nicht loeschen
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=60))
    assert ausloesung is not None
    assert ausloesung.severity is AlarmSeverity.WARNING


def test_upgrade_ueberlebt_orange_dip_und_haelt_max_severity():
    # Symmetrisch zur Erst-Eskalation: ein ORANGE-Dip auf aktivem (warning-)Niveau
    # unterbricht ein laufendes critical-Upgrade NICHT — sonst hebt ein ROT<->ORANGE
    # flackernder Sensor einen aktiven warning-Alarm nie auf critical (Unter-Eskalation).
    engine = _engine()
    _aktiver_warning(engine, _T0)
    engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=70))  # Upgrade-Timer startet
    engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=100))  # Dip haelt (kein Reset)
    upgrade = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=130))  # 130-70 >= 60
    assert upgrade is not None
    assert upgrade.severity is AlarmSeverity.CRITICAL


def test_langer_unknown_blackout_erzwingt_frischen_on_delay():
    # Begrenzter Freeze: eine UNKNOWN-Phase laenger als max_continuity_gap_s (120 s)
    # bricht die Kontinuitaet -> das uralte Pending darf NICHT sofort feuern (sonst
    # umgeht ein einzelner ORANGE-Blip nach Blackout den On-Delay komplett, Over-Alarm).
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    engine.beobachte(RiskLevel.UNKNOWN, _T0 + timedelta(seconds=60))
    engine.beobachte(RiskLevel.UNKNOWN, _T0 + timedelta(seconds=185))  # Luecke > 120 s
    # Erste ORANGE nach langem Blackout: kein Sofort-Alarm aus uraltem Pending.
    assert engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=200)) is None
    # Frischer On-Delay ab Wiederaufnahme -> feuert erst 60 s spaeter.
    spaet = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=260))
    assert spaet is not None
    assert spaet.severity is AlarmSeverity.WARNING


def test_quittiert_waehrend_upgrade_pending_setzt_alles_zurueck():
    engine = _engine()
    _aktiver_warning(engine, _T0)
    engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=70))  # Upgrade pending
    engine.quittiert()  # Mensch beendet den aktiven Alarm -> kompletter Reset
    # Frische ROT-Phase muss den vollen On-Delay erneut durchlaufen.
    engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=200))
    assert engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=230)) is None
    spaet = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=270))
    assert spaet is not None and spaet.severity is AlarmSeverity.CRITICAL


def test_upgrade_on_delay_ist_luecken_tolerant_gewollt():
    # DOKUMENTIERT/GEWOLLT (K1-Safe, Over-Alarm): Der On-Delay misst die Zeit seit der
    # ersten Bestaetigung und toleriert Luecken bis max_continuity_gap_s — er verlangt
    # NICHT strikt ununterbrochenes ROT. Ein ROT-Blip + gehaltenes ORANGE + spaeteres ROT
    # feuert daher critical, sobald on_delay seit dem ERSTEN ROT verstrichen ist. Bewusste
    # Anti-Chattering-Lockerung fuer flackernde Sensoren (R1/R2); critical bleibt sticky.
    engine = _engine()
    _aktiver_warning(engine, _T0)
    engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=70))  # ROT-Blip -> critical pending
    for s in (80, 90, 100, 110, 120):  # gehaltenes ORANGE (aktives Niveau)
        engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=s))
    upgrade = engine.beobachte(RiskLevel.RED, _T0 + timedelta(seconds=130))  # 130-70 >= 60
    assert upgrade is not None
    assert upgrade.severity is AlarmSeverity.CRITICAL


def test_luecke_genau_max_gap_haelt_kontinuitaet():
    # Grenzfall: eine Luecke von exakt max_continuity_gap_s (120 s) bricht die
    # Kontinuitaet NICHT (Pruefung ist strikt `> max_gap`). Inklusiv-/Exklusiv-Wahl pinnen.
    engine = _engine()
    engine.beobachte(RiskLevel.ORANGE, _T0)
    engine.beobachte(RiskLevel.UNKNOWN, _T0 + timedelta(seconds=60))
    ausloesung = engine.beobachte(RiskLevel.ORANGE, _T0 + timedelta(seconds=120))
    assert ausloesung is not None  # Luecke 120 nicht > 120, und 120 s >= on_delay 60


def test_rang_deckt_alle_severities_ab():
    # Schutz gegen stille KeyError, falls AlarmSeverity erweitert wird.
    from src.alarm.hysterese import _RANG

    assert set(_RANG) == set(AlarmSeverity)
