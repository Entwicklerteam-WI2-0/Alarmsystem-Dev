"""Tests für die Verdrahtung Bewertung -> Alarm-Generierung (DTB-27 in DTB-64).

`run_assessment_cycle` ist die testbare Pro-Zyklus-Naht, die der Scheduler aufruft:
DTB-64s `AssessmentService.assess_reading` erzeugt + persistiert die Bewertung, danach
generiert DTB-27s `AlarmGenerator` daraus Alarme (Severity + On-Delay-Hysterese).

Belegt: anhaltendes ORANGE löst nach `on_delay_s` genau einen (entprellten) Alarm aus;
eine UNKNOWN-Lage (Sensor fault -> Fail-safe) löst keinen Alarm aus (NF-01).
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator
from src.api.broadcaster import AlarmBroadcaster
from src.assessment.service import AssessmentService
from src.config.loader import load_thresholds
from src.main import build_runtime, run_assessment_cycle, run_scheduler
from src.model.enums import AlarmSeverity, AlarmState, RiskLevel, SensorStatus
from src.model.schemas import Alarm, Reading
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


def _vorfall1_reading(measured_at: datetime, rid: int) -> Reading:
    # Vorfall 1 (trockene Kälte): surface -2,1 <= Gefrierpunkt, aber sehr trocken (ΔT = 17,9
    # >> delta_t_feucht) -> weder ROT noch ORANGE, nur GELB -> KEIN Alarm.
    return Reading(
        id=rid,
        sensor_id="anr-rwy-01",
        measured_at=measured_at,
        surface_temp_c=-2.1,
        air_temp_c=-2.0,
        humidity_pct=40.0,
        received_at=measured_at,
        dew_point_c=-20.0,
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


def test_orange_dann_rot_upgrade_persistiert_zwei_alarme():
    service, generator, alarm_repo, _ = _wiring()

    # ORANGE bis On-Delay -> warning (Alarm 1).
    run_assessment_cycle(service, generator, _orange_reading(_T0, rid=1), _T0)
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(service, generator, _orange_reading(t60, rid=2), t60)
    # Lage verschärft sich auf ROT -> Upgrade-On-Delay -> critical (Alarm 2) durch die Naht.
    t90 = _T0 + timedelta(seconds=90)
    run_assessment_cycle(service, generator, _rot_reading(t90, rid=3), t90)
    t150 = _T0 + timedelta(seconds=150)
    run_assessment_cycle(service, generator, _rot_reading(t150, rid=4), t150)

    severities = [a.severity for a in alarm_repo.all()]
    assert severities == [AlarmSeverity.WARNING, AlarmSeverity.CRITICAL]


def test_vorfall_1_trockene_kaelte_loest_keinen_alarm_aus():
    service, generator, alarm_repo, assessment_repo = _wiring()

    # Vorfall 1 (Fehlalarm-Falle): trockene Kälte -> GELB, KEIN Alarm. Symmetrie zum
    # ROT-Wiring-Test; auch anhaltend kein Alarm (GELB erreicht den Alarmpfad nie).
    run_assessment_cycle(service, generator, _vorfall1_reading(_T0, rid=1), _T0)
    aktuell = assessment_repo.get_latest()
    assert aktuell is not None
    assert aktuell.risk_level is RiskLevel.YELLOW
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(service, generator, _vorfall1_reading(t60, rid=2), t60)
    assert alarm_repo.all() == []


def test_build_runtime_verdrahtet_alarm_generator():
    # Strukturtest des DI-Graphen: der AlarmGenerator (DTB-27) hängt im Runtime. build_runtime
    # kontaktiert keine DB (Repos verbinden erst pro Query), ist also DB-frei aufrufbar.
    runtime = build_runtime()
    assert isinstance(runtime.alarm_generator, AlarmGenerator)
    # Teilt das Audit-Log mit dem AssessmentService (eine gemeinsame Append-only-Quelle).
    assert runtime.alarm_generator._audit_repo is runtime.audit_repo  # noqa: SLF001


def test_build_runtime_verdrahtet_alarm_broadcaster():
    # DTB-61: der Live-Push-Broadcaster haengt im Runtime, damit run_scheduler (Producer) und
    # GET /v1/alarms/stream (Consumer) dieselbe Instanz teilen.
    runtime = build_runtime()
    assert isinstance(runtime.alarm_broadcaster, AlarmBroadcaster)


# ---------------------------------------------------------------------------
# run_assessment_cycle gibt den ausgeloesten Alarm zurueck (Push-Seam DTB-61)
# ---------------------------------------------------------------------------


def test_zyklus_gibt_ausgeloesten_alarm_zurueck():
    service, generator, _, _ = _wiring()

    # Erste ORANGE-Beobachtung: On-Delay startet -> kein Alarm -> None.
    assert run_assessment_cycle(service, generator, _orange_reading(_T0, rid=1), _T0) is None

    # 60 s später anhaltend ORANGE: Alarm feuert -> der Zyklus reicht ihn (mit id) durch,
    # damit run_scheduler ihn an den Broadcaster pushen kann.
    t60 = _T0 + timedelta(seconds=60)
    raised = run_assessment_cycle(service, generator, _orange_reading(t60, rid=2), t60)
    assert raised is not None
    assert raised.id is not None
    assert raised.severity is AlarmSeverity.WARNING


def test_zyklus_ohne_alarm_gibt_none_zurueck():
    service, generator, _, _ = _wiring()
    # UNKNOWN (Sensor fault) -> kein Alarm -> None (nichts zu pushen).
    assert (
        run_assessment_cycle(
            service, generator, _orange_reading(_T0, rid=1, status=SensorStatus.FAULT), _T0
        )
        is None
    )


# ---------------------------------------------------------------------------
# run_scheduler pusht den ausgeloesten Alarm an den Broadcaster (DTB-61)
# ---------------------------------------------------------------------------


def test_scheduler_pusht_ausgeloesten_alarm_an_broadcaster(monkeypatch):
    raised = Alarm(
        id=99,
        assessment_id=1,
        severity=AlarmSeverity.CRITICAL,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=lambda: None),  # Reading-Inhalt egal (cycle gepatcht)
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        # Den Zyklus auf einen festen Alarm patchen -> der Scheduler-Test prueft NUR die
        # Push-Verdrahtung (run_assessment_cycle ist separat getestet), ohne On-Delay-Timing.
        monkeypatch.setattr("src.main.run_assessment_cycle", lambda *a, **k: raised)

        async with broadcaster.subscribe() as queue:
            task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
            try:
                got = await asyncio.wait_for(queue.get(), timeout=1)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        assert got.id == 99
        assert got.severity is AlarmSeverity.CRITICAL

    asyncio.run(scenario())


def test_scheduler_pusht_nicht_wenn_kein_alarm(monkeypatch):
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=lambda: None),
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        # Kein Alarm im Zyklus -> kein publish -> der Abo-Queue bleibt leer.
        monkeypatch.setattr("src.main.run_assessment_cycle", lambda *a, **k: None)

        async with broadcaster.subscribe() as queue:
            task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
            await asyncio.sleep(0.05)  # mehrere Zyklen laufen lassen
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            assert queue.empty()

    asyncio.run(scenario())
