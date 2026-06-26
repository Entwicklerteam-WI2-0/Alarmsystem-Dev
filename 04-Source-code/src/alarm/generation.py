"""Alarm-Generierung (DTB-27): Schweregrad aus der Risikostufe ableiten.

Reine, zustandslose Funktion. Nur ORANGE/ROT lösen einen Alarm aus
(API_FROZEN_v1 §2a C, G2-intern): ORANGE -> warning, ROT -> critical.
GRÜN/GELB/unknown lösen KEINEN Alarm aus (FA-08: nur kritische Zustände;
`unknown` ist Fail-safe-Anzeige, kein Alarm). Die Severity-Ableitung ist NICHT
Teil des Wire-Contracts.

Die Entscheidung, ob aus einem ableitbaren Severity tatsächlich ein Alarm wird
(Entprellung/On-Delay), liegt in der Hysterese-Engine — diese Funktion bildet
nur die fachliche Zuordnung Stufe -> Schweregrad ab.
"""

from __future__ import annotations

from src.model.enums import AlarmSeverity, RiskLevel

# Risikostufe -> Alarm-Schweregrad. Nicht enthaltene Stufen (GRÜN/GELB/unknown)
# lösen bewusst keinen Alarm aus.
_SEVERITY_BY_RISK: dict[RiskLevel, AlarmSeverity] = {
    RiskLevel.ORANGE: AlarmSeverity.WARNING,
    RiskLevel.RED: AlarmSeverity.CRITICAL,
}


def severity_for_risk(risk_level: RiskLevel) -> AlarmSeverity | None:
    """Leitet den Alarm-Schweregrad aus der Risikostufe ab.

    Returns:
        `AlarmSeverity.WARNING` für ORANGE, `AlarmSeverity.CRITICAL` für ROT,
        sonst `None` (GRÜN/GELB/unknown lösen keinen Alarm aus).
    """
    return _SEVERITY_BY_RISK.get(risk_level)
