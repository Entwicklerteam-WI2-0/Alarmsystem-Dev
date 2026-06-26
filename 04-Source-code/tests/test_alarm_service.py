"""Tests für den Alarm-Generierungs-Service (DTB-27): Auslösung -> Persistenz + Audit.

Verbindet die echte AlarmHysterese mit InMemory-Repo/-Audit; Fehlerfälle über Stubs.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator
from src.config.loader import load_thresholds
from src.model.enums import AlarmSeverity, AlarmState, AuditEventType, RiskLevel
from src.model.schemas import Alarm, AuditLogEntry
from src.storage.alarm_repository import AlarmRepository, InMemoryAlarmRepository
from src.storage.audit_repository import AuditRepository, InMemoryAuditRepository
from src.storage.repository import RepositoryError

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)
_HYS = load_thresholds().hysterese  # on_delay 60, max_gap 120


def _engine() -> AlarmHysterese:
    return AlarmHysterese(_HYS)


class _FailingAlarmRepo(AlarmRepository):
    def save(self, alarm: Alarm) -> int:
        raise RepositoryError("save kaputt")


class _FailingAuditRepo(AuditRepository):
    def append(self, entry: AuditLogEntry) -> int:
        raise RepositoryError("audit kaputt")


def test_kein_alarm_keine_persistenz():
    alarm_repo, audit_repo = InMemoryAlarmRepository(), InMemoryAuditRepository()
    gen = AlarmGenerator(_engine(), alarm_repo, audit_repo)
    # Einzelne ORANGE-Beobachtung -> nur Pending, kein Alarm.
    assert gen.verarbeite(RiskLevel.ORANGE, 1, _T0) is None
    assert alarm_repo.all() == []
    assert audit_repo.all() == []


def test_alarm_persistiert_und_auditiert():
    alarm_repo, audit_repo = InMemoryAlarmRepository(), InMemoryAuditRepository()
    gen = AlarmGenerator(_engine(), alarm_repo, audit_repo)
    assert gen.verarbeite(RiskLevel.ORANGE, 7, _T0) is None  # Pending
    alarm_id = gen.verarbeite(RiskLevel.ORANGE, 7, _T0 + timedelta(seconds=60))  # feuert
    assert alarm_id == 1

    # Alarm korrekt persistiert:
    gespeichert = alarm_repo.all()[0]
    assert gespeichert.assessment_id == 7
    assert gespeichert.severity is AlarmSeverity.WARNING
    assert gespeichert.state is AlarmState.ACTIVE
    assert gespeichert.raised_at == _T0 + timedelta(seconds=60)

    # Audit alarm_raised geschrieben:
    eintrag = audit_repo.all()[0]
    assert eintrag.event_type is AuditEventType.ALARM_RAISED
    assert eintrag.entity_type == "alarm"
    assert eintrag.entity_id == 1
    assert eintrag.detail == {"severity": "warning", "risk_level": "orange"}


def test_persistenz_fehler_armt_engine_neu_und_propagiert():
    engine = _engine()
    gen = AlarmGenerator(engine, _FailingAlarmRepo(), InMemoryAuditRepository())
    gen.verarbeite(RiskLevel.ORANGE, 1, _T0)  # Pending
    with pytest.raises(RepositoryError):
        gen.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=60))  # feuert, save kaputt

    # Engine wurde neu gearmt (beenden) -> mit funktionierendem Repo feuert die anhaltende
    # Bedingung erneut (sonst stiller Under-Alarm).
    gen_ok = AlarmGenerator(engine, InMemoryAlarmRepository(), InMemoryAuditRepository())
    assert gen_ok.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=120)) is None
    assert gen_ok.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=180)) is not None


def test_audit_fehler_propagiert_ohne_rearm():
    engine = _engine()
    alarm_repo = InMemoryAlarmRepository()
    gen = AlarmGenerator(engine, alarm_repo, _FailingAuditRepo())
    gen.verarbeite(RiskLevel.ORANGE, 1, _T0)  # Pending
    with pytest.raises(RepositoryError):
        gen.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=60))  # feuert; audit kaputt

    # Alarm wurde trotzdem persistiert ...
    assert len(alarm_repo.all()) == 1
    # ... und die Engine ist NICHT neu gearmt (Alarm bleibt aktiv): gehaltene gleiche Stufe
    # (kontinuierlich <= max_gap) loest keinen zweiten Alarm aus.
    gen2 = AlarmGenerator(engine, alarm_repo, InMemoryAuditRepository())
    assert gen2.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=110)) is None
    assert gen2.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=180)) is None
