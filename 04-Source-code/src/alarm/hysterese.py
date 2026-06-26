"""Alarm-Hysterese/Entprellung (DTB-27, Schwellenwerte.md §2, ISA-18.2).

Zustandsbehaftete Engine, die einen Strom von Risikostufen entprellt und das
*Auslösen* von Alarmen verzögert (On-Delay), um Chattering zu vermeiden. Die
zeitlose Vereisungsbewertung (assessment, DTB-38) bleibt dadurch zustandslos.

Die Zeit wird bei jeder Beobachtung explizit übergeben (`jetzt`) statt intern
`datetime.now()` zu rufen — so ist die Engine eine reine, deterministisch
testbare Zustandsmaschine (kein Uhr-Mock nötig).

RB-01 / FA-10: reine Entscheidungsunterstützung. Die Engine löst Alarme nur aus;
sie beendet KEINEN aktiven Alarm automatisch. Das Clearing/die Rückstufung ist
eine bewusste, hier später ergänzte Stabilisierung bzw. eine manuelle Aktion —
nie ein stiller Auto-Clear.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.alarm.generation import severity_for_risk
from src.config.loader import HystereseParameter
from src.model.enums import AlarmSeverity, RiskLevel


@dataclass(frozen=True)
class AlarmAusloesung:
    """Ergebnis einer Beobachtung: jetzt einen Alarm dieses Schweregrads erzeugen."""

    severity: AlarmSeverity
    ausgeloest_am: datetime


# Rangordnung der Schweregrade für die Hochstufungs-Logik: kein Alarm < warning < critical.
_RANG: dict[AlarmSeverity, int] = {AlarmSeverity.WARNING: 1, AlarmSeverity.CRITICAL: 2}


def _rang(severity: AlarmSeverity | None) -> int:
    """Numerischer Rang einer (optionalen) Severity; None = kein Alarm = 0."""
    return _RANG[severity] if severity is not None else 0


class AlarmHysterese:
    """Entprellt die Alarm-Generierung per On-Delay (DTB-27).

    Ein Alarm wird erst ausgelöst, wenn eine alarmwürdige Stufe (ORANGE/ROT)
    mindestens `on_delay_s` Sekunden ununterbrochen anliegt. Fällt die Bedingung
    vorher weg, startet der Timer neu. Solange ein Alarm aktiv ist, löst die Engine
    keinen weiteren aus (RB-01: kein Auto-Clear; Beenden ist manuell, FA-10).
    """

    def __init__(self, params: HystereseParameter) -> None:
        self._on_delay = timedelta(seconds=params.on_delay_s)
        self._pending_seit: datetime | None = None
        self._aktiver_alarm: AlarmSeverity | None = None

    def beobachte(self, risk_level: RiskLevel, jetzt: datetime) -> AlarmAusloesung | None:
        """Verarbeitet eine Risikostufe zum Zeitpunkt `jetzt`.

        Returns:
            Eine `AlarmAusloesung` genau auf der Beobachtung, die den On-Delay
            überschreitet; sonst `None` (pending, nicht alarmwürdig oder bereits aktiv).
        """
        severity = severity_for_risk(risk_level)

        # Nur eine Hochstufung (höhere Stufe als der aktive Alarm) ist On-Delay-relevant:
        # Raise (kein Alarm -> warning/critical) oder Upgrade (warning -> critical). Stufen
        # <= aktiv (auch nicht-alarmwürdige GRÜN/GELB/unknown) setzen den Eskalations-Timer
        # zurück und lösen nichts aus — KEIN automatisches Downgrade/Clear (RB-01/FA-10);
        # der aktive Alarm bleibt bestehen, bis ihn ein Mensch über `quittiert()` beendet.
        if _rang(severity) <= _rang(self._aktiver_alarm):
            self._pending_seit = None
            return None

        # severity ist hier alarmwürdig (Rang > 0) und höher als der aktive Alarm.
        if self._pending_seit is None:
            self._pending_seit = jetzt
            return None

        if jetzt - self._pending_seit >= self._on_delay:
            self._aktiver_alarm = severity
            self._pending_seit = None
            return AlarmAusloesung(severity=severity, ausgeloest_am=jetzt)

        return None

    def quittiert(self) -> None:
        """Meldet, dass ein Mensch den aktiven Alarm beendet hat (manuell, RB-01/FA-10).

        Setzt den internen Zustand zurück, sodass eine erneut auftretende Bedingung wieder
        einen Alarm auslösen kann. Dies ist der EINZIGE Weg, den aktiven Alarm zu beenden —
        es gibt bewusst kein automatisches Clearing (RB-01: Mensch = letzte Instanz).
        """
        self._aktiver_alarm = None
        self._pending_seit = None
