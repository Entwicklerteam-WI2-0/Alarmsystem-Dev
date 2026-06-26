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
        # Höchste Stufe der laufenden Eskalationsphase — damit ein transientes ROT im
        # On-Delay-Fenster nicht zu WARNING „verwässert" (Safety-Bias).
        self._pending_max: AlarmSeverity | None = None
        self._aktiver_alarm: AlarmSeverity | None = None

    def beobachte(self, risk_level: RiskLevel, jetzt: datetime) -> AlarmAusloesung | None:
        """Verarbeitet eine Risikostufe zum Zeitpunkt `jetzt`.

        Returns:
            Eine `AlarmAusloesung` genau auf der Beobachtung, die den On-Delay
            überschreitet; sonst `None` (pending, nicht alarmwürdig oder bereits aktiv).

        Raises:
            ValueError: wenn `jetzt` nicht zeitzonenbewusst ist (Contract §2a D: UTC).
            Der Aufrufer muss zudem monoton steigende Zeit liefern (Poll-Schicht).
        """
        if jetzt.tzinfo is None:
            raise ValueError(
                "jetzt muss zeitzonenbewusst (UTC) sein — naive datetime nicht erlaubt."
            )

        severity = severity_for_risk(risk_level)

        # Eskalations-Kandidat: alarmwürdig UND höher als der aktive Alarm — Raise
        # (kein Alarm -> warning/critical) oder Upgrade (warning -> critical).
        if severity is not None and _rang(severity) > _rang(self._aktiver_alarm):
            if self._pending_seit is None:
                self._pending_seit = jetzt
                self._pending_max = severity
            elif _rang(severity) > _rang(self._pending_max):
                self._pending_max = severity  # höchste Stufe der Phase festhalten

            if jetzt - self._pending_seit >= self._on_delay:
                ausgeloest = self._pending_max
                self._aktiver_alarm = ausgeloest
                self._pending_seit = None
                self._pending_max = None
                # _pending_max ist hier nie None (mit _pending_seit gesetzt).
                return AlarmAusloesung(severity=ausgeloest, ausgeloest_am=jetzt)
            return None

        # Kein Eskalations-Kandidat:
        #  - UNKNOWN (Unsicherheit/Stale) FRIERT eine laufende Eskalation EIN — kein Reset.
        #    Sonst könnte ein flackernder Sensor (ORANGE<->UNKNOWN, R1/R2) den On-Delay
        #    endlos zurücksetzen und einen realen Alarm dauerhaft unterdrücken (NF-01/K1).
        #  - GRÜN/GELB oder Stufe <= aktiv = bestätigte Nicht-/Niedriger-Lage -> Timer-Reset.
        #    KEIN Auto-Downgrade/Clear eines aktiven Alarms (RB-01/FA-10).
        if risk_level is not RiskLevel.UNKNOWN:
            self._pending_seit = None
            self._pending_max = None
        return None

    def quittiert(self) -> None:
        """Meldet, dass ein Mensch den aktiven Alarm beendet hat (manuell, RB-01/FA-10).

        Setzt den Alarm-Zustand zurück, sodass eine erneut auftretende Bedingung wieder
        einen Alarm auslösen kann. Dies ist der EINZIGE Weg, den aktiven Alarm zu beenden —
        kein automatisches Clearing (RB-01: Mensch = letzte Instanz). Ohne aktiven Alarm ist
        der Aufruf ein No-Op: eine gerade laufende Eskalation wird NICHT unterbrochen.
        """
        if self._aktiver_alarm is None:
            return
        self._aktiver_alarm = None
        self._pending_seit = None
        self._pending_max = None
