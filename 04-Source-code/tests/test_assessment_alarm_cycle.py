"""Tests für die Verdrahtung Bewertung -> Alarm-Generierung (DTB-27 in DTB-64).

`run_assessment_cycle` ist die testbare Pro-Zyklus-Naht, die der Scheduler aufruft:
DTB-64s `AssessmentService.assess_reading` erzeugt + persistiert die Bewertung, danach
generiert DTB-27s `AlarmGenerator` daraus Alarme (Severity + On-Delay-Hysterese).

Belegt: anhaltendes ORANGE löst nach `on_delay_s` genau einen (entprellten) Alarm aus;
eine UNKNOWN-Lage (Sensor fault -> Fail-safe) löst keinen Alarm aus (NF-01).
"""

from datetime import UTC, datetime, timedelta

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator
from src.assessment.service import AssessmentService
from src.config.loader import load_thresholds
from src.main import build_runtime, run_assessment_cycle
from src.model.enums import AlarmSeverity, RiskLevel, SensorStatus
from src.model.schemas import Reading
from src.storage.alarm_repository import InMemoryAlarmRepository
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)
_THR = load_thresholds()  # Default-Schwellen: gefrierpunkt 0, feucht 1; on_delay 60 s


def _orange_reading(
    measured_at: datetime, rid: int, *, status: SensorStatus = SensorStatus.OK
) -> Reading:
    # surface 0.0 (<= Gefrierpunkt) + ΔT = 0.0-(-0.5) = 0.5 (feucht, aber nicht ROT) -> ORANGE.
    return Reading(
        id=rid,
        sensor_id="anr-rwy-01",
        measured_at=measured_at,
        surface_temp_c=0.0,
        air_temp_c=2.0,
        humidity_pct=90.0,
        received_at=measured_at,
        dew_point_c=-0.5,
        status=status,
    )


def _rot_reading(measured_at: datetime, rid: int) -> Reading:
    # surface -1.0 (<= Gefrierpunkt) + ΔT = -1.0-(-1.0) = 0.0 (<= delta_t_kondensation) -> ROT.
    return Reading(
        id=rid,
        sensor_id="anr-rwy-01",
        measured_at=measured_at,
        surface_temp_c=-1.0,
        air_temp_c=0.0,
        humidity_pct=95.0,
        received_at=measured_at,
        dew_point_c=-1.0,
        status=SensorStatus.OK,
    )


def _wiring() -> tuple[
    AssessmentService,
    AlarmGenerator,
    InMemoryAlarmRepository,
    InMemoryAssessmentRepository,
]:
    audit_repo = InMemoryAuditRepository()
    assessment_repo = InMemoryAssessmentRepository()
    service = AssessmentService(_THR, assessment_repo, audit_repo)
    alarm_repo = InMemoryAlarmRepository()
    generator = AlarmGenerator(AlarmHysterese(_THR.hysterese), alarm_repo, audit_repo)
    return service, generator, alarm_repo, assessment_repo


def test_anhaltendes_orange_persistiert_alarm_nach_on_delay():
    service, generator, alarm_repo, _ = _wiring()

    # Erste ORANGE-Beobachtung: On-Delay startet, noch kein Alarm.
    run_assessment_cycle(service, generator, _orange_reading(_T0, rid=1), _T0)
    assert alarm_repo.all() == []

    # Gleiche Lage 60 s später: On-Delay erreicht -> genau ein entprellter Alarm (warning).
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(service, generator, _orange_reading(t60, rid=2), t60)
    alarme = alarm_repo.all()
    assert len(alarme) == 1
    assert alarme[0].severity is AlarmSeverity.WARNING


def test_sensor_fault_loest_keinen_alarm_aus():
    service, generator, alarm_repo, _ = _wiring()

    # Sensor fault -> assess_reading erzeugt unknown (Fail-safe) -> kein Alarm, auch anhaltend.
    run_assessment_cycle(
        service, generator, _orange_reading(_T0, rid=1, status=SensorStatus.FAULT), _T0
    )
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(
        service, generator, _orange_reading(t60, rid=2, status=SensorStatus.FAULT), t60
    )
    assert alarm_repo.all() == []


def test_anhaltendes_rot_persistiert_critical_alarm():
    service, generator, alarm_repo, _ = _wiring()

    # Vorfall-2-naher ROT (aktive Eisbildung). Erste Beobachtung: On-Delay startet, kein Alarm.
    run_assessment_cycle(service, generator, _rot_reading(_T0, rid=1), _T0)
    assert alarm_repo.all() == []

    # 60 s später anhaltend ROT -> genau ein Alarm, Severity CRITICAL (end-to-end durch die Naht).
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(service, generator, _rot_reading(t60, rid=2), t60)
    alarme = alarm_repo.all()
    assert len(alarme) == 1
    assert alarme[0].severity is AlarmSeverity.CRITICAL


def test_stale_reading_loest_keinen_alarm_aus():
    service, generator, alarm_repo, assessment_repo = _wiring()

    # Sensor-OK, aber measured_at > stale_timeout (120 s) alt -> assess_reading erzeugt UNKNOWN
    # (Fail-safe), NICHT GELB. Pinnt die DTB-27-Vorbedingung an der Verdrahtungs-Naht: ein
    # fälschliches GELB würde den On-Delay zurücksetzen und eine reale Eskalation unterdrücken.
    alt = _orange_reading(_T0 - timedelta(seconds=121), rid=1)  # OK, aber 121 s alt
    run_assessment_cycle(service, generator, alt, _T0)
    aktuell = assessment_repo.get_latest()
    assert aktuell is not None
    assert aktuell.risk_level is RiskLevel.UNKNOWN  # Vorbedingung: Stale -> UNKNOWN, nicht GELB

    # Auch anhaltend stale -> kein Alarm.
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(
        service, generator, _orange_reading(t60 - timedelta(seconds=121), rid=2), t60
    )
    assert alarm_repo.all() == []


def test_build_runtime_verdrahtet_alarm_generator():
    # Strukturtest des DI-Graphen: der AlarmGenerator (DTB-27) hängt im Runtime. build_runtime
    # kontaktiert keine DB (Repos verbinden erst pro Query), ist also DB-frei aufrufbar.
    runtime = build_runtime()
    assert isinstance(runtime.alarm_generator, AlarmGenerator)
    # Teilt das Audit-Log mit dem AssessmentService (eine gemeinsame Append-only-Quelle).
    assert runtime.alarm_generator._audit_repo is runtime.audit_repo  # noqa: SLF001
