"""Tests für die Verdrahtung Bewertung -> Alarm-Generierung (DTB-27 in DTB-64).

`run_assessment_cycle` ist die testbare Pro-Zyklus-Naht, die der Scheduler aufruft:
DTB-64s `AssessmentService.assess_reading` erzeugt + persistiert die Bewertung, danach
generiert DTB-27s `AlarmGenerator` daraus Alarme (Severity + On-Delay-Hysterese).

Belegt: anhaltendes ORANGE löst nach `on_delay_s` genau einen (entprellten) Alarm aus;
eine UNKNOWN-Lage (Sensor fault -> Fail-safe) löst keinen Alarm aus (NF-01).
"""

import asyncio
import contextlib
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator, AuditError
from src.api.broadcaster import AlarmBroadcaster
from src.assessment.service import AssessmentService
from src.config.loader import load_thresholds
from src.main import build_runtime, run_assessment_cycle, run_scheduler
from src.model.enums import AlarmSeverity, AlarmState, RiskLevel, SensorStatus
from src.model.schemas import Alarm, Reading
from src.storage.alarm_repository import InMemoryAlarmRepository
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository
from src.storage.repository import RepositoryError

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


async def _wait_until(predicate: Callable[[], bool], *, timeout: float = 2.0) -> bool:
    """Pollt bis `predicate()` wahr ist (statt Fixsleep) — entkoppelt Assertions von der
    nicht-deterministischen Thread-Pool-Latenz der `asyncio.to_thread`-Hops (Windows-CI).
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.005)
    return predicate()


def test_anhaltendes_orange_persistiert_alarm_nach_on_delay():
    service, generator, alarm_repo, assessment_repo = _wiring()

    # Erste ORANGE-Beobachtung: On-Delay startet, noch kein Alarm.
    run_assessment_cycle(service, generator, _orange_reading(_T0, rid=1), _T0)
    # Vorbedingung pinnen (Symmetrie zu den Negativ-Tests): das Reading MUSS ORANGE ergeben.
    # Wird _THR durch die G1-Finalwerte rekalibriert (laut CLAUDE.md geplant) und ergibt z. B.
    # GELB, scheitert der Test dann sichtbar am RiskLevel statt mit irrefuehrendem 'len==1'.
    aktuell = assessment_repo.get_latest()
    assert aktuell is not None
    assert aktuell.risk_level is RiskLevel.ORANGE
    assert alarm_repo.all() == []

    # Gleiche Lage 60 s später: On-Delay erreicht -> genau ein entprellter Alarm (warning).
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(service, generator, _orange_reading(t60, rid=2), t60)
    alarme = alarm_repo.all()
    assert len(alarme) == 1
    assert alarme[0].severity is AlarmSeverity.WARNING


def test_sensor_fault_loest_keinen_alarm_aus():
    service, generator, alarm_repo, assessment_repo = _wiring()

    # Sensor fault -> assess_reading erzeugt unknown (Fail-safe) -> kein Alarm, auch anhaltend.
    run_assessment_cycle(
        service, generator, _orange_reading(_T0, rid=1, status=SensorStatus.FAULT), _T0
    )
    # Vorbedingung pinnen (Symmetrie zu Stale-/Vorfall-1-Test): fault MUSS UNKNOWN ergeben,
    # nicht z. B. GRUEN. Ohne diesen Pin faerbt eine NF-01-Regression (fault -> GRUEN) den
    # Test NICHT rot — GRUEN loest ebenfalls keinen Alarm aus (Schein-Sicherheit).
    aktuell = assessment_repo.get_latest()
    assert aktuell is not None
    assert aktuell.risk_level is RiskLevel.UNKNOWN
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(
        service, generator, _orange_reading(t60, rid=2, status=SensorStatus.FAULT), t60
    )
    assert alarm_repo.all() == []


def test_anhaltendes_rot_persistiert_critical_alarm():
    service, generator, alarm_repo, assessment_repo = _wiring()

    # Vorfall-2-naher ROT (aktive Eisbildung). Erste Beobachtung: On-Delay startet, kein Alarm.
    run_assessment_cycle(service, generator, _rot_reading(_T0, rid=1), _T0)
    # Vorbedingung pinnen (Symmetrie zu den Negativ-Tests): das Reading MUSS ROT ergeben,
    # sonst wird ein Kalibrier-Drift (G1-Finalwerte) als RiskLevel-Fehler sichtbar statt als
    # verwirrender Alarm-Zaehlfehler.
    aktuell = assessment_repo.get_latest()
    assert aktuell is not None
    assert aktuell.risk_level is RiskLevel.RED
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
    service, generator, alarm_repo, assessment_repo = _wiring()

    # ORANGE bis On-Delay -> warning (Alarm 1).
    run_assessment_cycle(service, generator, _orange_reading(_T0, rid=1), _T0)
    # Vorbedingung pinnen: die ORANGE-Phase MUSS ORANGE ergeben (Kalibrier-Drift sonst als
    # RiskLevel-Fehler statt als Alarm-Severity-Fehler sichtbar).
    aktuell = assessment_repo.get_latest()
    assert aktuell is not None
    assert aktuell.risk_level is RiskLevel.ORANGE
    t60 = _T0 + timedelta(seconds=60)
    run_assessment_cycle(service, generator, _orange_reading(t60, rid=2), t60)
    # Lage verschärft sich auf ROT -> Upgrade-On-Delay -> critical (Alarm 2) durch die Naht.
    t90 = _T0 + timedelta(seconds=90)
    run_assessment_cycle(service, generator, _rot_reading(t90, rid=3), t90)
    # Vorbedingung der Upgrade-Phase pinnen: das verschaerfte Reading MUSS ROT ergeben.
    aktuell = assessment_repo.get_latest()
    assert aktuell is not None
    assert aktuell.risk_level is RiskLevel.RED
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

        # Thread-Pin der load-bearing Invariante (main.py Z.176-182 + broadcaster-Docstring):
        # publish MUSS auf dem Event-Loop-Thread laufen, NICHT im asyncio.to_thread-Worker.
        # Der bloße Queue-Empfang (got.id==99) kann einen Loop-Push nicht von einem Worker-Push
        # unterscheiden — put_nowait legt das Item im Einzel-Item-Szenario auch cross-thread ab,
        # ohne zu werfen. Ein Refactor, der publish in den to_thread-Worker zieht, fuehrt
        # put_nowait off-loop aus (NICHT thread-safe: Future-Wakeups der wartenden Getter) ->
        # unter Last verlorene Live-Alarm-Events (NF-01). Dieser Spy faerbt das deterministisch rot.
        captured: dict[str, threading.Thread] = {}
        real_publish = broadcaster.publish

        def _spy(alarm: Alarm) -> None:
            captured["thread"] = threading.current_thread()
            real_publish(alarm)

        monkeypatch.setattr(broadcaster, "publish", _spy)

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
        # Unter asyncio.run laeuft der Event-Loop im Main-Thread, to_thread-Worker in Pool-
        # Threads. publish lief auf dem Main-/Loop-Thread -> bare put_nowait ist hier safe.
        assert captured["thread"] is threading.main_thread()

    asyncio.run(scenario())


def test_scheduler_pusht_nicht_wenn_kein_alarm(monkeypatch):
    calls = {"i": 0}

    def _kein_alarm(*_a: object, **_k: object) -> None:
        calls["i"] += 1
        return None

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=lambda: None),
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        # Kein Alarm im Zyklus -> kein publish -> der Abo-Queue bleibt leer.
        monkeypatch.setattr("src.main.run_assessment_cycle", _kein_alarm)

        async with broadcaster.subscribe() as queue:
            task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
            try:
                # Statt Fixsleep: warten bis der 2. Zyklus BEGONNEN hat (calls>=2). Der Beginn des
                # 2. Zyklus beweist, dass der 1. Zyklus seinen Schleifenkoerper inkl. der
                # if-raised-Publish-Verzweigung vollstaendig durchlief -> die Negativ-Aussage
                # 'kein Alarm -> kein publish' pinnt damit genau die durchlaufene Verzweigung
                # (calls>0 belegt nur, dass der Zyklus im to_thread-Worker zu zaehlen begann).
                assert await _wait_until(lambda: calls["i"] >= 2)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            assert queue.empty()

    asyncio.run(scenario())


def test_scheduler_pusht_nicht_bei_audit_error(monkeypatch, caplog):
    # AuditError-Pfad (main.py): Alarm gespeichert, aber Audit fehlgeschlagen -> der Zyklus wirft,
    # run_scheduler pusht NICHT an den Broadcaster (ein un-auditierter Alarm darf G3 nur via Resync
    # GET /v1/alarms erreichen, NF-09/E-37) und loggt ERROR mit alarm_id; Scheduler laeuft weiter.
    calls = {"i": 0}

    def _audit_boom(*_a: object, **_k: object) -> Alarm:
        calls["i"] += 1
        raise AuditError("Audit-Eintrag fehlgeschlagen (Test).", alarm_id=99)

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=lambda: None),
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        monkeypatch.setattr("src.main.run_assessment_cycle", _audit_boom)

        with caplog.at_level(logging.ERROR, logger="src.main"):
            async with broadcaster.subscribe() as queue:
                task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
                try:
                    # Statt Fixsleep: bis der 2. Zyklus BEGONNEN hat (calls>=2). Der Beginn des
                    # 2. Zyklus beweist, dass der 1. Zyklus seinen Schleifenkoerper inkl. des
                    # AuditError-Handlers (ERROR-Log, KEIN publish) vollstaendig durchlief ->
                    # entkoppelt von der Thread-Pool-Latenz und pinnt die durchlaufene
                    # Verzweigung (nicht nur, dass der Worker zu zaehlen begann).
                    assert await _wait_until(lambda: calls["i"] >= 2)
                finally:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                assert queue.empty()  # un-auditierter Alarm NICHT live gepusht
        # ERROR-Zeile mit der alarm_id belegt: AuditError erkannt, Alarm verbleibt fuer Resync.
        assert any("99" in record.getMessage() for record in caplog.records)

    asyncio.run(scenario())


def test_scheduler_ueberlebt_werfenden_zyklus(monkeypatch):
    # NF-01-Kernzusage: ein werfender Zyklus darf die Schleife NICHT beenden. Der 1. Zyklus wirft
    # RepositoryError, ab dem 2. liefert er einen festen Alarm -> erscheint der Alarm am Abo, hat
    # der erste (werfende) Zyklus den Loop nachweislich nicht gekillt (sonst Timeout statt Alarm).
    raised = Alarm(
        id=7,
        assessment_id=1,
        severity=AlarmSeverity.WARNING,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )
    calls = {"i": 0}

    def _erst_werfen_dann_alarm(*_a: object, **_k: object) -> Alarm:
        calls["i"] += 1
        if calls["i"] == 1:
            raise RepositoryError("Persistenz kurz weg (Test).")
        return raised

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=lambda: None),
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        monkeypatch.setattr("src.main.run_assessment_cycle", _erst_werfen_dann_alarm)

        async with broadcaster.subscribe() as queue:
            task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
            try:
                got = await asyncio.wait_for(queue.get(), timeout=1)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        assert got.id == 7  # Alarm aus dem 2. Zyklus -> Loop hat den 1. (werfenden) ueberlebt

    asyncio.run(scenario())


def test_scheduler_ueberlebt_generischen_fehler_und_loggt_exception(monkeypatch, caplog):
    # NF-01-Restnetz: der generische `except Exception`-Catch-all (main.py Z. 205-206) faengt
    # einen UNERWARTETEN Fehler ab — NICHT Audit/Repository/Value, sondern ein residualer Bug
    # (hier RuntimeError, stellvertretend fuer TypeError/KeyError/...). Ohne diesen Catch-all
    # stuerbe der Loop beim ersten unerwarteten Fehler lautlos und publizierte nie wieder Alarme
    # (Producer faktisch tot). Der 1. Zyklus wirft, ab dem 2. liefert er einen festen Alarm.
    raised = Alarm(
        id=9,
        assessment_id=1,
        severity=AlarmSeverity.WARNING,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )
    calls = {"i": 0}

    def _erst_runtimeerror_dann_alarm(*_a: object, **_k: object) -> Alarm:
        calls["i"] += 1
        if calls["i"] == 1:
            raise RuntimeError("Unerwarteter residualer Fehler (Test).")
        return raised

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=lambda: None),
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        monkeypatch.setattr("src.main.run_assessment_cycle", _erst_runtimeerror_dann_alarm)

        with caplog.at_level(logging.ERROR, logger="src.main"):
            async with broadcaster.subscribe() as queue:
                task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
                try:
                    got = await asyncio.wait_for(queue.get(), timeout=1)
                finally:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
        assert got.id == 9  # Loop ueberlebt den generischen Fehler (fail-safe weiter)
        # Genau der generische Pfad lief (logger.exception 'Unerwarteter Fehler') und KEIN
        # spezifischer Handler bzw. CRITICAL — belegt das Catch-all-Restnetz, nicht einen
        # der drei Spezialhandler.
        assert any(
            record.name == "src.main"
            and record.levelno == logging.ERROR
            and "Unerwarteter Fehler im Scheduler" in record.getMessage()
            for record in caplog.records
        )
        assert not any(record.levelno == logging.CRITICAL for record in caplog.records)

    asyncio.run(scenario())


def test_scheduler_ueberlebt_werfende_poll_schicht(monkeypatch):
    # NF-01-Restnetz an der Poll-Schicht (main.py Z. 155): obwohl poll() intern fail-safe None
    # liefert, sichert der generische Catch-all auch einen residualen Crash der Poll-Schicht ab.
    # poll() wirft beim 1. Aufruf, ab dem 2. liefert es ein Reading; der Zyklus ist auf einen
    # festen Alarm gepatcht -> erscheint der Alarm, hat der Loop den Poll-Crash ueberlebt.
    raised = Alarm(
        id=10,
        assessment_id=1,
        severity=AlarmSeverity.WARNING,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )
    poll_calls = {"i": 0}

    def _poll_erst_werfen_dann_reading() -> Reading:
        poll_calls["i"] += 1
        if poll_calls["i"] == 1:
            raise RuntimeError("Poll-Schicht-Crash (Test).")
        return _orange_reading(_T0, rid=1)

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=_poll_erst_werfen_dann_reading),
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        # Zyklus auf einen festen Alarm patchen -> isoliert das Poll-Restnetz vom Engine-Timing.
        monkeypatch.setattr("src.main.run_assessment_cycle", lambda *a, **k: raised)

        async with broadcaster.subscribe() as queue:
            task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
            try:
                got = await asyncio.wait_for(queue.get(), timeout=1)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        assert got.id == 10  # Loop ueberlebt den Poll-Crash -> Alarm aus dem 2. Durchlauf

    asyncio.run(scenario())


def test_scheduler_ueberlebt_invariantenbruch_und_loggt_critical(monkeypatch, caplog):
    # ValueError-Zweig (main.py): ein Invariantenbruch (Bug, nicht transient) wird als CRITICAL
    # geloggt UND fail-safe uebersprungen — distinkt VOR dem generischen except Exception. Eine
    # Regression (re-raise, vertauschte Handler-Reihenfolge sodass ValueError ins generische
    # except faellt, ausgelassenes await asyncio.sleep) bliebe ohne diesen Test unerkannt.
    raised = Alarm(
        id=8,
        assessment_id=1,
        severity=AlarmSeverity.WARNING,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )
    calls = {"i": 0}

    def _erst_valueerror_dann_alarm(*_a: object, **_k: object) -> Alarm:
        calls["i"] += 1
        if calls["i"] == 1:
            raise ValueError("Invariantenbruch (Test).")
        return raised

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=lambda: None),
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        monkeypatch.setattr("src.main.run_assessment_cycle", _erst_valueerror_dann_alarm)

        with caplog.at_level(logging.CRITICAL, logger="src.main"):
            async with broadcaster.subscribe() as queue:
                task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
                try:
                    # Alarm aus dem 2. Zyklus -> der 1. (ValueError) hat den Loop nicht gekillt.
                    got = await asyncio.wait_for(queue.get(), timeout=1)
                finally:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
        assert got.id == 8  # Loop ueberlebt den Invariantenbruch (fail-safe weiter)
        # Eigener CRITICAL-Pfad (nicht generisches except): Ops sieht Bug vs. transient.
        assert any(
            record.levelno == logging.CRITICAL and record.name == "src.main"
            for record in caplog.records
        )

    asyncio.run(scenario())


def test_scheduler_klemmt_rueckwaerts_wallclock_und_loggt_warning(monkeypatch, caplog):
    # Monotonie-Klemme (main.py): faellt die Wall-Clock zwischen zwei Zyklen (NTP-
    # Rueckwaertskorrektur), darf die Hysterese-Vorbedingung (nicht-fallende Zeit) NICHT reissen
    # -> der Scheduler klemmt now auf last_now und reicht die geklemmte Zeit an die Engine weiter.
    # NF-01-Fail-safe gegen Under-Alarm: ohne die Klemme setzt der Rueckwaertssprung die
    # On-Delay-Akkumulation der Hysterese zurueck und unterdrueckt eine reale Eskalation. Eine
    # Regression (Klemme entfernt, Vergleich invertiert, last_now-Update verschoben) faerbt sonst
    # KEINEN Test rot — alle uebrigen Scheduler-Tests laufen gegen reale, monoton steigende Zeit.
    t0 = _T0
    zurueck = _T0 - timedelta(seconds=30)

    class _FakeClock:
        """datetime-Ersatz: now() liefert erst t0, dann (dauerhaft) den Rueckwaertswert."""

        def __init__(self, werte: list[datetime]) -> None:
            self._werte = werte

        def now(self, _tz: object = None) -> datetime:
            return self._werte.pop(0) if len(self._werte) > 1 else self._werte[0]

    captured: list[datetime] = []

    def _capture_now(_service: object, _generator: object, _reading: object, now: datetime) -> None:
        captured.append(now)
        return None

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(
            poller=SimpleNamespace(poll=lambda: None),
            service=object(),
            alarm_generator=object(),
            alarm_broadcaster=broadcaster,
        )
        monkeypatch.setattr("src.main.datetime", _FakeClock([t0, zurueck]))
        monkeypatch.setattr("src.main.run_assessment_cycle", _capture_now)

        with caplog.at_level(logging.WARNING, logger="src.main"):
            task = asyncio.create_task(run_scheduler(runtime, interval_s=0.01))
            try:
                # Warten bis BEIDE Zyklen (t0, dann der gefallene Wert) an die Engine gereicht sind.
                assert await _wait_until(lambda: len(captured) >= 2)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        # 1. Zyklus: now = t0 unveraendert. 2. Zyklus: gefallene Wall-Clock auf last_now (t0)
        # geklemmt -> NICHT der Rueckwaertswert (t0-30s) erreicht die Engine.
        assert captured[0] == t0
        assert captured[1] == t0  # geklemmt, nicht zurueck
        # Skew fuer Ops sichtbar gemacht (WARNING mit 'geklemmt').
        assert any(
            record.levelno == logging.WARNING and "geklemmt" in record.getMessage()
            for record in caplog.records
        )

    asyncio.run(scenario())
