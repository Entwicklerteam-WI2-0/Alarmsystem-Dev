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
from datetime import UTC, datetime, timedelta

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
    mindestens `on_delay_s` Sekunden anliegt — gemessen ab der ersten Bestätigung und
    lücken-tolerant bis `max_continuity_gap_s` (Details siehe `beobachte`). Fällt die
    Bedingung bestätigt weg (GRÜN/GELB), startet der Timer neu. Solange ein Alarm aktiv
    ist, löst die Engine keinen weiteren *gleicher oder niedrigerer* Stufe aus; eine
    Hochstufung (warning -> critical) ist möglich. Kein Auto-Clear/-Downgrade — der aktive
    Alarm wird nur manuell über `quittiert()` beendet (RB-01, FA-10).
    """

    def __init__(self, params: HystereseParameter) -> None:
        self._on_delay = timedelta(seconds=params.on_delay_s)
        # Maximal tolerierte Lücke zwischen zwei alarmwürdigen Bestätigungen, bevor die
        # Kontinuität als gebrochen gilt (z. B. lange UNKNOWN-Phase) -> begrenzt den Freeze.
        self._max_gap = timedelta(seconds=params.max_continuity_gap_s)
        self._pending_seit: datetime | None = None
        # Höchste Stufe der laufenden Eskalationsphase — damit ein transientes ROT im
        # On-Delay-Fenster nicht zu WARNING „verwässert" (Safety-Bias).
        self._pending_max: AlarmSeverity | None = None
        # Zeit der letzten alarmwürdigen Bestätigung (zur Kontinuitäts-/Lückenprüfung).
        self._letzte_alarmwuerdige: datetime | None = None
        self._aktiver_alarm: AlarmSeverity | None = None

    def _reset_pending(self) -> None:
        """Verwirft eine laufende Eskalation (nicht den aktiven Alarm)."""
        self._pending_seit = None
        self._pending_max = None
        self._letzte_alarmwuerdige = None

    def beobachte(self, risk_level: RiskLevel, jetzt: datetime) -> AlarmAusloesung | None:
        """Verarbeitet eine Risikostufe zum Zeitpunkt `jetzt`.

        Returns:
            Eine `AlarmAusloesung` genau auf der Beobachtung, die den On-Delay
            überschreitet; sonst `None` (pending, nicht alarmwürdig oder bereits aktiv).

        Raises:
            ValueError: wenn `jetzt` nicht zeitzonenbewusst ist (Contract §2a D: UTC).
            Der Aufrufer muss zudem monoton steigende Zeit liefern (Poll-Schicht).

        Hinweis (bewusst): Der On-Delay misst die Zeit seit der ersten Bestätigung und
        toleriert Lücken bis `max_continuity_gap_s` — er verlangt NICHT strikt
        ununterbrochene Anwesenheit der höheren Stufe. Ein ROT-Blip, gehaltenes ORANGE
        und späteres ROT kann daher früher critical auslösen als bei strenger Kontinuität.
        Das ist die gewollte Anti-Chattering-Lockerung für flackernde Sensoren (R1/R2);
        Richtung Over-Alarm (K1-konform), nie unter den aktiven Alarm (RB-01).
        """
        if jetzt.tzinfo is None:
            raise ValueError(
                "jetzt muss zeitzonenbewusst (UTC) sein — naive datetime nicht erlaubt."
            )
        # Auf UTC normalisieren (Contract §2a D): ein tz-aware-aber-Nicht-UTC `jetzt` würde
        # sonst seinen Fremd-Offset in `ausgeloest_am` tragen. Die Differenz bleibt korrekt.
        jetzt = jetzt.astimezone(UTC)

        severity = severity_for_risk(risk_level)
        sev_rang = _rang(severity)
        aktiv_rang = _rang(self._aktiver_alarm)

        # Eskalations-Kandidat: alarmwürdig UND höher als der aktive Alarm — Raise
        # (kein Alarm -> warning/critical) oder Upgrade (warning -> critical).
        if sev_rang > aktiv_rang:
            # Kontinuität gebrochen (kein Pending, oder die Lücke zur letzten alarmwürdigen
            # Bestätigung übersteigt max_gap, z. B. nach langem UNKNOWN-Blackout) -> frischer
            # On-Delay statt aus uraltem Pending sofort zu feuern.
            if (
                self._pending_seit is None
                or self._letzte_alarmwuerdige is None
                or jetzt - self._letzte_alarmwuerdige > self._max_gap
            ):
                self._pending_seit = jetzt
                self._pending_max = severity
            elif sev_rang > _rang(self._pending_max):
                self._pending_max = severity  # höchste Stufe der Phase festhalten
            self._letzte_alarmwuerdige = jetzt

            if jetzt - self._pending_seit >= self._on_delay:
                ausgeloest = self._pending_max
                self._aktiver_alarm = ausgeloest
                self._reset_pending()
                # _pending_max war hier nie None (mit _pending_seit gesetzt).
                return AlarmAusloesung(severity=ausgeloest, ausgeloest_am=jetzt)
            return None

        # Beobachtung auf aktivem Niveau (z. B. ORANGE bei aktivem warning): „hält" eine
        # laufende Eskalation, ohne auszulösen — zählt als alarmwürdige Bestätigung
        # (symmetrisch zur Erst-Eskalation), bricht ein laufendes Upgrade also nicht ab.
        if sev_rang == aktiv_rang and aktiv_rang > 0:
            if self._pending_seit is not None:
                self._letzte_alarmwuerdige = jetzt
            return None

        # Sonst: nicht-alarmwürdig oder Abfall unter den aktiven Alarm.
        #  - UNKNOWN (Unsicherheit/Stale) FRIERT eine laufende Eskalation EIN — kein Reset.
        #    Sonst könnte ein flackernder Sensor (ORANGE<->UNKNOWN, R1/R2) den On-Delay
        #    zurücksetzen und einen realen Alarm unterdrücken (NF-01/K1). Begrenzt durch die
        #    Kontinuitäts-/Lückenprüfung oben (lange Lücke -> frischer On-Delay).
        #  - GRÜN/GELB / Abfall = bestätigte De-Eskalation -> Pending-Reset. KEIN
        #    Auto-Downgrade/Clear eines aktiven Alarms (RB-01/FA-10).
        if risk_level is not RiskLevel.UNKNOWN:
            self._reset_pending()
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
        self._reset_pending()
