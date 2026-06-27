"""Tests fuer die Lifespan-/Runtime-Initialisierung (src.main, DTB-64).

Belegt die LAUFZEIT-Verdrahtung (im Gegensatz zu den Endpoint-Tests, die get_runtime
via dependency_overrides umgehen):
- Der TestClient als Context-Manager durchlaeuft lifespan -> app.state.runtime ist ein
  vollstaendiger Runtime-Graph.
- Der Scheduler ist hinter G2_ENABLE_SCHEDULER gated (Default AUS); ist er an, wird ein
  Hintergrund-Task erzeugt.
- build_runtime() verdrahtet den realen Graph, ohne DB/G1 zu kontaktieren.

build_runtime wird auf den In-Memory-runtime-Fixture gepatcht (keine DB), run_scheduler
durch eine No-op-Coroutine ersetzt (keine echte httpx-Schleife gegen G1).
"""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from src.assessment.service import AssessmentService
from src.ingest.poller import Poller
from src.main import Runtime, app, build_runtime
from src.storage.assessment_repository import AssessmentRepository
from src.storage.audit_repository import AuditRepository
from src.storage.repository import Repository


@pytest.fixture(autouse=True)
def _reset_app_state() -> Iterator[None]:
    """Nach jedem Test app.state.runtime + dependency_overrides zuruecksetzen.

    try/finally (nicht manuell am Testende): laesst ein Test mitten im with-Block einen
    Fehler werfen, wuerde sonst der Runtime in app.state leaken und den reihenfolge-
    abhaengigen test_current_runtime_not_initialized_returns_503 (module-level Client
    ohne Lifespan) in test_assessment_current_endpoint.py brechen.
    """
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "runtime"):
            del app.state.runtime


def _recording_scheduler() -> tuple[list[tuple], Callable[..., object]]:
    """Liefert (calls, factory): factory ersetzt run_scheduler, zeichnet jeden Aufruf
    synchron auf und gibt eine sofort fertige No-op-Coroutine zurueck (keine Schleife).
    """
    calls: list[tuple] = []

    async def _noop() -> None:
        return None

    def _factory(*args: object, **kwargs: object) -> object:
        # Synchron beim Aufruf von run_scheduler(...) in lifespan erfasst (vor dem yield).
        calls.append((args, kwargs))
        return _noop()

    return calls, _factory


def test_lifespan_sets_full_runtime_on_app_state(
    monkeypatch: pytest.MonkeyPatch, runtime: Runtime
) -> None:
    monkeypatch.delenv("G2_ENABLE_SCHEDULER", raising=False)
    monkeypatch.setattr("src.main.build_runtime", lambda: runtime)

    with TestClient(app):
        rt = app.state.runtime
        assert rt is runtime
        assert isinstance(rt, Runtime)
        # Alle Bausteine verdrahtet (DI-Graph vollstaendig).
        assert isinstance(rt.poller, Poller)
        assert isinstance(rt.service, AssessmentService)
        assert rt.reading_repo is not None
        assert rt.assessment_repo is not None
        assert rt.audit_repo is not None


def test_scheduler_disabled_by_default(monkeypatch: pytest.MonkeyPatch, runtime: Runtime) -> None:
    monkeypatch.delenv("G2_ENABLE_SCHEDULER", raising=False)
    monkeypatch.setattr("src.main.build_runtime", lambda: runtime)
    calls, factory = _recording_scheduler()
    monkeypatch.setattr("src.main.run_scheduler", factory)

    with TestClient(app):
        pass

    assert calls == []  # ohne Env kein Scheduler-Task


def test_scheduler_enabled_creates_task(monkeypatch: pytest.MonkeyPatch, runtime: Runtime) -> None:
    monkeypatch.setenv("G2_ENABLE_SCHEDULER", "1")
    monkeypatch.setattr("src.main.build_runtime", lambda: runtime)
    calls, factory = _recording_scheduler()
    monkeypatch.setattr("src.main.run_scheduler", factory)

    with TestClient(app):
        pass

    assert len(calls) == 1  # genau ein Scheduler-Task gestartet
    assert calls[0][0][0] is runtime  # run_scheduler(runtime, interval)


def test_build_runtime_wires_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    # Realer build_runtime() kontaktiert weder DB noch G1 (Repos verbinden erst pro Query) ->
    # deckt die Verdrahtung ab, die der gepatchte In-Memory-Pfad nicht mitprueft.
    monkeypatch.delenv("G1_BASE_URL", raising=False)

    rt = build_runtime()

    assert isinstance(rt, Runtime)
    assert isinstance(rt.reading_repo, Repository)
    assert isinstance(rt.assessment_repo, AssessmentRepository)
    assert isinstance(rt.audit_repo, AuditRepository)
    assert isinstance(rt.poller, Poller)
    assert isinstance(rt.service, AssessmentService)
    assert rt.thresholds is not None
