"""Runtime-DI-Graph + Zugriffs-Dependency (geteilt zwischen main.py und den Routern).

`Runtime` ist der zusammengebaute Dependency-Graph einer laufenden Instanz; `get_runtime`
ist die Dependency, ueber die Endpoints (assessment/current in main.py, thresholds in
api/v1.py) darauf zugreifen — testbar via `app.dependency_overrides`, ohne DB/Lifespan.
Gebaut wird der Graph in `main.build_runtime()` (Composition Root); hier liegen nur Typ +
Accessor, damit die Router ihn ohne Layer-ueberkreuzenden Import (api -> main) nutzen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from src.api.exceptions import RuntimeNotReadyError

if TYPE_CHECKING:
    from src.assessment import AssessmentService
    from src.config.loader import Thresholds
    from src.ingest.poller import Poller
    from src.storage import AssessmentRepository, AuditRepository, ReadingRepository


@dataclass
class Runtime:
    """Zusammengebauter Dependency-Graph einer laufenden Instanz (DI)."""

    thresholds: Thresholds
    reading_repo: ReadingRepository
    assessment_repo: AssessmentRepository
    audit_repo: AuditRepository
    poller: Poller
    service: AssessmentService


def get_runtime(request: Request) -> Runtime:
    """DI-Zugriff auf den in `lifespan` zusammengebauten Runtime-Graph.

    Eigene Dependency (kein direkter `app.state`-Zugriff im Endpoint), damit Tests
    sie via `app.dependency_overrides` durch In-Memory-Fakes ersetzen koennen —
    ohne DB, Lifespan oder Scheduler.

    Raises:
        RuntimeNotReadyError: Wenn `app.state.runtime` fehlt (lifespan nicht oder nur
            teilweise durchlaufen). Der Exception-Handler liefert daraufhin 503
            (`Error {code, message}`) statt eines rohen 500/`{detail}`.
    """
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise RuntimeNotReadyError("Runtime nicht initialisiert (lifespan unvollstaendig).")
    return runtime
