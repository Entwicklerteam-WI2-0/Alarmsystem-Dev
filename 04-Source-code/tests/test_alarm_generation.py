"""Tests für die Alarm-Generierung (DTB-27): Severity-Mapping aus der Risikostufe.

Vertrag (API_FROZEN_v1 §2a C, G2-intern): nur ORANGE/ROT lösen einen Alarm aus
(ORANGE -> warning, ROT -> critical). GRÜN/GELB/unknown lösen KEINEN Alarm aus.
Die Severity-Ableitung ist NICHT Teil des Wire-Contracts, aber fachlich verbindlich.
"""

from src.alarm.generation import severity_for_risk
from src.model.enums import AlarmSeverity, RiskLevel


def test_rot_ergibt_critical():
    # Arrange / Act
    severity = severity_for_risk(RiskLevel.RED)
    # Assert
    assert severity is AlarmSeverity.CRITICAL


def test_orange_ergibt_warning():
    severity = severity_for_risk(RiskLevel.ORANGE)
    assert severity is AlarmSeverity.WARNING


def test_gruen_loest_keinen_alarm_aus():
    assert severity_for_risk(RiskLevel.GREEN) is None


def test_gelb_loest_keinen_alarm_aus():
    # GELB ist Vorwarnung/Beobachtung, kein Alarm (FA-08: nur kritische Zustaende).
    assert severity_for_risk(RiskLevel.YELLOW) is None


def test_unknown_loest_keinen_alarm_aus():
    # unknown = Fail-safe-Zustand (NF-01): zeigt Unsicherheit an, ist aber kein
    # ORANGE/ROT-Alarm. Die Fail-safe-Sichtbarkeit liegt an der risk_level-Ampel.
    assert severity_for_risk(RiskLevel.UNKNOWN) is None
