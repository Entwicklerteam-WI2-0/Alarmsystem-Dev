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

        # Nicht alarmwürdig (GRÜN/GELB/unknown): On-Delay-Timer zurücksetzen. Ein
        # bereits aktiver Alarm bleibt bestehen — kein Auto-Clear (RB-01/FA-10).
        if severity is None:
            self._pending_seit = None
            return None

        # Bereits ein Alarm aktiv: im Kern keine erneute Auslösung.
        if self._aktiver_alarm is not None:
            return None

        # Alarmwürdige Bedingung — On-Delay-Timer starten bzw. Ablauf prüfen.
        if self._pending_seit is None:
            self._pending_seit = jetzt
            return None

        if jetzt - self._pending_seit >= self._on_delay:
            self._aktiver_alarm = severity
            self._pending_seit = None
            return AlarmAusloesung(severity=severity, ausgeloest_am=jetzt)

        return None
