"""Alarm-Generierungs-Service (DTB-27): Bewertung → Auslösung → Persistenz + Audit.

Reine Naht per Dependency-Injection: der Aufrufer (Poll-/Orchestrierungsschicht) besitzt
die per-Sensor-`AlarmHysterese`-Instanz und ruft `verarbeite` je Bewertung. Der Service
selbst hält keinen Loop und keine Sensor-Lifecycle-Logik — er ist deterministisch testbar.

Fail-safe (NF-01): Schlägt die Persistenz fehl, wird die Engine über `beenden()` neu gearmt,
damit die fortbestehende Bedingung erneut auslösen kann (sonst stiller Under-Alarm). Der
Audit-Eintrag `alarm_raised` (FA-12/NF-09) wird nach erfolgreicher Persistenz geschrieben;
ein Audit-Fehler nimmt den bereits gespeicherten Alarm NICHT zurück (kein Re-Arm).
"""

from __future__ import annotations

from datetime import datetime

from src.alarm.hysterese import AlarmHysterese
from src.model.enums import AuditEventType, RiskLevel
from src.model.schemas import Alarm, AuditLogEntry
from src.storage.alarm_repository import AlarmRepository
from src.storage.audit_repository import AuditRepository
from src.storage.repository import RepositoryError


class AlarmGenerator:
    """Verbindet Hysterese-Engine, Alarm-Persistenz und Audit-Log zu einem Auslöse-Schritt."""

    def __init__(
        self,
        engine: AlarmHysterese,
        alarm_repo: AlarmRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._engine = engine
        self._alarm_repo = alarm_repo
        self._audit_repo = audit_repo

    def verarbeite(self, risk_level: RiskLevel, assessment_id: int, jetzt: datetime) -> int | None:
        """Verarbeitet eine Bewertung; persistiert + auditiert einen ausgelösten Alarm.

        Returns:
            Die vergebene Alarm-ID, wenn ein Alarm ausgelöst und gespeichert wurde; sonst `None`.

        Raises:
            ValueError: wenn `jetzt` kein zeitzonenbewusstes Datetime ist (Contract §2a D;
            in `AlarmHysterese.beobachte` validiert und hier durchgereicht).
            RepositoryError: bei Persistenz- oder Audit-Fehler (Persistenz-Fehler armt zuvor
            die Engine neu, damit die Bedingung erneut auslösen kann).
        """
        ausloesung = self._engine.beobachte(risk_level, jetzt)
        if ausloesung is None:
            return None

        alarm = Alarm(
            assessment_id=assessment_id,
            severity=ausloesung.severity,
            raised_at=ausloesung.ausgeloest_am,
        )
        try:
            alarm_id = self._alarm_repo.save(alarm)
        except RepositoryError:
            # NF-01-Recovery: Persistenz fehlgeschlagen -> Engine neu armen, sonst feuert die
            # fortbestehende Bedingung nie erneut (stiller Under-Alarm).
            self._engine.beenden()
            raise

        # Audit alarm_raised (FA-12/NF-09). Alarm ist bereits persistiert + Engine aktiv;
        # ein Audit-Fehler wird gemeldet, kehrt den Alarm aber NICHT zurück (kein Re-Arm).
        # Hinweis (kein Bug): `severity` ist der PHASEN-PEAK (Safety-Bias, `pending_max`),
        # `risk_level`/`assessment_id` die AUSLÖSENDE Beobachtung — sie können legitim
        # divergieren (ROT-Blip im On-Delay-Fenster, danach ORANGE-Auslösung -> critical@orange).
        self._audit_repo.append(
            AuditLogEntry(
                ts=ausloesung.ausgeloest_am,
                event_type=AuditEventType.ALARM_RAISED,
                entity_type="alarm",
                entity_id=alarm_id,
                detail={"severity": ausloesung.severity.value, "risk_level": risk_level.value},
            )
        )
        return alarm_id
