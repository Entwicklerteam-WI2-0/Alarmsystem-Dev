"""Tests für den Alarm-Generierungs-Service (DTB-27): Auslösung -> Persistenz + Audit.

Verbindet die echte AlarmHysterese mit InMemory-Repo/-Audit; Fehlerfälle über Stubs.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator, AuditError
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
    alarm = gen.verarbeite(RiskLevel.ORANGE, 7, _T0 + timedelta(seconds=60))  # feuert

    # verarbeite gibt den persistierten Alarm (mit vergebener id) zurueck — der Push-Seam
    # (DTB-61) braucht das vollstaendige Alarm-Objekt, nicht nur die id.
    assert alarm is not None
    assert alarm.id == 1
    assert alarm.assessment_id == 7
    assert alarm.severity is AlarmSeverity.WARNING
    assert alarm.state is AlarmState.ACTIVE
    assert alarm.raised_at == _T0 + timedelta(seconds=60)

    # ... und derselbe Alarm ist persistiert:
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
    with pytest.raises(RepositoryError) as excinfo:
        gen.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=60))  # feuert, save kaputt
    assert not isinstance(excinfo.value, AuditError)  # Persistenz-Fehler != Audit-Fehler

    # Engine wurde neu gearmt (beenden) -> mit funktionierendem Repo feuert die anhaltende
    # Bedingung erneut (sonst stiller Under-Alarm).
    gen_ok = AlarmGenerator(engine, InMemoryAlarmRepository(), InMemoryAuditRepository())
    assert gen_ok.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=120)) is None
    assert gen_ok.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=180)) is not None


def test_unerwarteter_save_fehler_armt_engine_neu():
    # Auch ein NICHT-RepositoryError (z. B. kuenftige API-Aenderung im Repo) muss die Engine
    # neu armen (Over-Alarm-Bias) statt sie "aktiv" ohne DB-Alarm zu hinterlassen.
    class _BuggyAlarmRepo(AlarmRepository):
        def save(self, alarm: Alarm) -> int:
            raise TypeError("unerwarteter Bug im Repo")

    engine = _engine()
    gen = AlarmGenerator(engine, _BuggyAlarmRepo(), InMemoryAuditRepository())
    gen.verarbeite(RiskLevel.ORANGE, 1, _T0)  # Pending
    with pytest.raises(TypeError):
        gen.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=60))  # feuert; save buggy

    # Engine neu gearmt -> mit funktionierendem Repo feuert die anhaltende Bedingung erneut.
    gen_ok = AlarmGenerator(engine, InMemoryAlarmRepository(), InMemoryAuditRepository())
    assert gen_ok.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=120)) is None
    assert gen_ok.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=180)) is not None


def test_audit_fehler_als_auditerror_mit_id_ohne_rearm():
    engine = _engine()
    alarm_repo = InMemoryAlarmRepository()
    gen = AlarmGenerator(engine, alarm_repo, _FailingAuditRepo())
    gen.verarbeite(RiskLevel.ORANGE, 1, _T0)  # Pending
    with pytest.raises(AuditError) as excinfo:
        gen.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=60))  # feuert; audit kaputt

    # AuditError ist EIGENSTAENDIG (NICHT RepositoryError) -> ein except RepositoryError faengt
    # ihn nicht versehentlich mit (kein Ordering-Footgun); traegt die ID des gespeicherten Alarms.
    assert not isinstance(excinfo.value, RepositoryError)
    assert excinfo.value.alarm_id == 1
    # Alarm wurde trotzdem persistiert ...
    assert len(alarm_repo.all()) == 1
    # ... und die Engine ist NICHT neu gearmt (Alarm bleibt aktiv): gehaltene gleiche Stufe
    # (kontinuierlich <= max_gap) loest keinen zweiten Alarm aus.
    gen2 = AlarmGenerator(engine, alarm_repo, InMemoryAuditRepository())
    assert gen2.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=110)) is None
    assert gen2.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=180)) is None


def test_unerwarteter_audit_fehler_wird_auditerror():
    # Auch ein NICHT-RepositoryError aus dem Audit-Repo muss als AuditError (mit alarm_id)
    # aufschlagen -> sonst bricht der AuditError-Vertrag und der Scheduler verliert die alarm_id.
    class _BuggyAuditRepo(AuditRepository):
        def append(self, entry: AuditLogEntry) -> int:
            raise RuntimeError("unerwarteter Bug im Audit-Repo")

    engine = _engine()
    alarm_repo = InMemoryAlarmRepository()
    gen = AlarmGenerator(engine, alarm_repo, _BuggyAuditRepo())
    gen.verarbeite(RiskLevel.ORANGE, 1, _T0)  # Pending
    with pytest.raises(AuditError) as excinfo:
        gen.verarbeite(RiskLevel.ORANGE, 1, _T0 + timedelta(seconds=60))  # feuert; audit buggy

    assert excinfo.value.alarm_id == 1
    assert len(alarm_repo.all()) == 1  # Alarm trotz unerwartetem Audit-Fehler persistiert
