"""Alarm-Generierungs-Service (DTB-27): Bewertung → Auslösung → Persistenz + Audit.

Reine Naht per Dependency-Injection: der Aufrufer (Poll-/Orchestrierungsschicht) besitzt
die per-Sensor-`AlarmHysterese`-Instanz und ruft `verarbeite` je Bewertung. Der Service
selbst hält keinen Loop und keine Sensor-Lifecycle-Logik — er ist deterministisch testbar.

Fail-safe (NF-01): Schlägt die Persistenz fehl, wird die Engine über `beenden()` neu gearmt,
damit die fortbestehende Bedingung erneut auslösen kann (sonst stiller Under-Alarm). Der
Audit-Eintrag `alarm_raised` (FA-12/NF-09) wird nach erfolgreicher Persistenz geschrieben;
ein Audit-Fehler nimmt den bereits gespeicherten Alarm NICHT zurück (kein Re-Arm) und wird
als `AuditError` (mit `alarm_id`) signalisiert — unterscheidbar vom reinen Persistenz-Fehler.
"""

from __future__ import annotations

from datetime import datetime

from src.alarm.hysterese import AlarmHysterese
from src.model.enums import AuditEventType, RiskLevel
from src.model.schemas import Alarm, AuditLogEntry
from src.storage.alarm_repository import AlarmRepository
from src.storage.audit_repository import AuditRepository


class AuditError(Exception):
    """Audit-Fehler NACH erfolgreicher Persistenz (DTB-27): Alarm gespeichert + Engine aktiv.

    EIGENSTAENDIGE Exception (bewusst NICHT von `RepositoryError` abgeleitet): so faengt ein
    `except RepositoryError` in einem kuenftigen Aufrufer (DTB-31, G3-Naht) den AuditError
    NICHT versehentlich mit und verliert den `alarm` — der Aufrufer MUSS ihn explizit
    behandeln (kein Reihenfolge-Footgun). Semantik: Der Alarm ist DB-seitig vorhanden
    (`alarm` mit id) UND die Engine bleibt 'aktiv' (KEIN Re-Arm) — NICHT erneut `beenden()` rufen.
    Ein reiner Persistenz-Fehler ist dagegen ein `RepositoryError` (Alarm NICHT gespeichert,
    Engine bereits neu gearmt).

    Traegt den vollstaendigen persistierten `alarm` (mit id), NICHT nur die id: der Aufrufer
    (run_scheduler) pusht ihn trotz der Audit-Luecke live an G3 (NF-01 vor NF-09) -> der
    SSE-Stream bleibt vollstaendig (keine stille Sichtbarkeits-Luecke bis zum Resync).
    """

    def __init__(self, message: str, alarm: Alarm) -> None:
        super().__init__(message)
        self.alarm = alarm
        self.alarm_id = alarm.id  # Backward-Compat + Log-Convenience


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

    def verarbeite(
        self, risk_level: RiskLevel, assessment_id: int, jetzt: datetime
    ) -> Alarm | None:
        """Verarbeitet eine Bewertung; persistiert + auditiert einen ausgelösten Alarm.

        Returns:
            Den persistierten `Alarm` (mit vergebener `id`), wenn ein Alarm ausgelöst und
            gespeichert wurde; sonst `None`. Den vollständigen Alarm (statt nur der id)
            braucht der Live-Push-Seam (DTB-61): `run_scheduler` reicht ihn an den
            `AlarmBroadcaster` weiter, der ihn als SSE-Event an G3 streamt.

        Raises:
            ValueError: wenn `jetzt` kein zeitzonenbewusstes Datetime ist (Contract §2a D;
            in `AlarmHysterese.beobachte` validiert und hier durchgereicht).
            RepositoryError: bei Persistenz-Fehler — die Engine wird zuvor neu gearmt
            (`beenden`), der Alarm ist NICHT gespeichert.
            AuditError: bei Audit-Fehler NACH erfolgreicher Persistenz — der Alarm IST
            gespeichert (`alarm_id` am Fehler) und die Engine bleibt aktiv (KEIN Re-Arm).
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
        except Exception:  # noqa: BLE001 - JEDER Save-Fehler -> Re-Arm (Over-Alarm-Bias, K1)
            # NF-01-Recovery: Die Persistenz ist nicht bestaetigt (egal welcher Fehler, NICHT
            # nur RepositoryError -> auch ein unerwarteter Bug wie TypeError) -> Engine neu armen,
            # sonst bliebe sie "aktiv" ohne DB-Alarm und die fortbestehende Bedingung feuert nie
            # erneut (stiller Under-Alarm). Der Fehler wird unveraendert weitergereicht (Scheduler
            # loggt ihn; ein Bug bleibt sichtbar), die Engine aber nicht im Fehlzustand.
            # Over-Alarm-Abwaegung (K1): War bereits ein schwaecherer Alarm aktiv und scheitert
            # die Persistenz eines Upgrades, vergisst der Re-Arm den noch in der DB lebenden
            # Alarm -> bei anhaltender Lage kann ein zweiter (schwaecherer) Alarm entstehen.
            # Richtung Over-Alarm (sicher); Dedup aktiver Alarme im Lesepfad = DTB-31.
            self._engine.beenden()
            raise

        # Audit alarm_raised (FA-12/NF-09). Alarm ist bereits persistiert + Engine aktiv;
        # ein Audit-Fehler wird gemeldet, kehrt den Alarm aber NICHT zurück (kein Re-Arm).
        # Hinweis (kein Bug): `severity` ist der PHASEN-PEAK (Safety-Bias, `pending_max`),
        # `risk_level`/`assessment_id` die AUSLÖSENDE Beobachtung — sie können legitim
        # divergieren (ROT-Blip im On-Delay-Fenster, danach ORANGE-Auslösung -> critical@orange).
        # Persistierten Alarm MIT vergebener id (Push-Seam DTB-61); Original unangetastet
        # (model_copy). VOR dem Audit berechnet, damit ihn auch der AuditError-Pfad an G3
        # pushen kann (NF-01 vor NF-09: ein Audit-Fehler darf die Zustellung nicht verhindern).
        gespeicherter_alarm = alarm.model_copy(update={"id": alarm_id})
        try:
            self._audit_repo.append(
                AuditLogEntry(
                    ts=ausloesung.ausgeloest_am,
                    event_type=AuditEventType.ALARM_RAISED,
                    entity_type="alarm",
                    entity_id=alarm_id,
                    detail={"severity": ausloesung.severity.value, "risk_level": risk_level.value},
                )
            )
        except Exception as exc:  # noqa: BLE001 - JEDER Audit-Fehler -> AuditError (Contract)
            # Alarm ist bereits persistiert + Engine aktiv -> KEIN Re-Arm. JEDE Audit-Exception
            # (nicht nur RepositoryError; auch ein unerwarteter RuntimeError/TypeError) als
            # AuditError MIT dem persistierten Alarm signalisieren — sonst bricht der AuditError-
            # Vertrag und der Scheduler verliert im generischen except-Zweig den Alarm.
            raise AuditError(
                "Alarm gespeichert, aber Audit-Eintrag fehlgeschlagen", alarm=gespeicherter_alarm
            ) from exc
        return gespeicherter_alarm
