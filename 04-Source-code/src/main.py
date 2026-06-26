"""FastAPI-Einstiegspunkt des G2-Backends (Vereisungserkennung ANR).

DTB-64-SCAFFOLD (Laufzeit-Verdrahtung) — Start-Geruest fuer den Ausbau:
Die fachlichen Bausteine sind fertig + unit-getestet
(`AssessmentService.assess_reading`, `build_assessment_current`, Repositories,
Poller). HIER fehlt nur die LAUFZEIT-Verdrahtung — als Skelett mit `TODO DTB-64`
markiert:

  Poller --(poll alle poll_interval_s)--> AssessmentService.assess_reading
        --> AssessmentRepository.save + AuditRepository.append
  GET /v1/assessment/current --> build_assessment_current(latest_assessment, latest_reading)

Der Scheduler ist bewusst hinter `G2_ENABLE_SCHEDULER` gated (Default AUS), damit
`uvicorn`/Tests ohne DB/G1 nicht crashen. Zum Scharfschalten: Env setzen +
DB-/G1-Variablen bereitstellen (s. database.py / G1_BASE_URL).

Erledigt:
  - GET /v1/assessment/current (DTB-43): liest runtime.assessment_repo.get_latest()
    + runtime.reading_repo.get_latest(sensor_id); 503 (Error{code,message}) bei
    DB-Ausfall / keinen Daten, sonst build_assessment_current(...) mit Serve-Zeit-NF-01.

Offene TODOs fuer den Ausbau:
  1. poll_interval_s aus Config laden (neues Feld betrieb.poll_interval_s, P0-a)
     statt aus Env/Default.
  2. GET /v1/health auf Pydantic `Health` + 503-Pfad heben (Contract-Treue).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from src.assessment import AssessmentService, build_assessment_current
from src.config.loader import Thresholds, load_thresholds
from src.ingest.poller import Poller
from src.model.schemas import AssessmentCurrent, Error
from src.storage import (
    AssessmentRepository,
    AuditRepository,
    MySqlAssessmentRepository,
    MySqlAuditRepository,
    ReadingRepository,
    RepositoryError,
)

logger = logging.getLogger(__name__)

# TODO DTB-64 / P0-a: poll_interval_s gehoert in die Config (betrieb.poll_interval_s),
# nicht als Default hier. Bis dahin ueber Env uebersteuerbar.
_DEFAULT_POLL_INTERVAL_S = 30.0
# Bewusster Default: http:// im abgeschlossenen Projekt-/Intranet (G1 ist ein
# Prototyp ohne TLS). Fuer realen Betrieb HTTPS NICHT hier hart erzwingen — ein
# https://-Default wuerde die Verbindung zu einem HTTP-only-G1 brechen (eingefrorene
# Naht). Stattdessen pro Umgebung per Env umstellen: G1_BASE_URL=https://g1-sensorik.local
# (dokumentiert in .env.example). Architektenentscheidung, falls HTTPS-Default + HTTP-Opt-in
# gewuenscht wird.
_DEFAULT_G1_BASE_URL = "http://g1-sensorik.local"

# Single-Sensor-Betrieb (anr-rwy-01). Bewusst eine benannte Konstante statt eines
# inline-Strings. TODO F24/Geo: Sensor-/Standort-Liste aus config/ laden statt hier
# zu fixieren — das get_latest()-Assessment ist ohnehin noch global (nicht pro Sensor),
# daher ist die ID hier nur die Reading-Auswahl fuer den Aktualitaets-/Status-Check.
_SENSOR_ID = "anr-rwy-01"

# Contract-Fehlercode fuer "G2 nicht lieferfaehig" (503), s. openapi.yaml Error-Beispiel.
_SERVICE_UNAVAILABLE_CODE = "SERVICE_UNAVAILABLE"


@dataclass
class Runtime:
    """Zusammengebauter Dependency-Graph einer laufenden Instanz (DI)."""

    thresholds: Thresholds
    reading_repo: ReadingRepository
    assessment_repo: AssessmentRepository
    audit_repo: AuditRepository
    poller: Poller
    service: AssessmentService


def build_runtime() -> Runtime:
    """Baut den DI-Graph (ohne DB/G1 zu kontaktieren — Repos verbinden erst pro Query)."""
    thresholds = load_thresholds()
    reading_repo = ReadingRepository()
    assessment_repo = MySqlAssessmentRepository()
    audit_repo = MySqlAuditRepository()
    poller = Poller(
        base_url=os.environ.get("G1_BASE_URL", _DEFAULT_G1_BASE_URL),
        repository=reading_repo,
        data_quality_thresholds=thresholds.datenqualitaet,
        plausibility_thresholds=thresholds.plausibilitaet,
    )
    service = AssessmentService(thresholds, assessment_repo, audit_repo)
    return Runtime(
        thresholds=thresholds,
        reading_repo=reading_repo,
        assessment_repo=assessment_repo,
        audit_repo=audit_repo,
        poller=poller,
        service=service,
    )


class RuntimeNotReadyError(RuntimeError):
    """`app.state.runtime` fehlt — lifespan hat den DI-Graph (noch) nicht gesetzt.

    Eigene Exception statt rohem AttributeError: faengt `build_runtime()` im lifespan
    vor dem yield eine unbehandelte Exception (oder ist `runtime` aus anderem Grund
    nicht gesetzt), wuerde ein direkter `app.state.runtime`-Zugriff als FastAPI-
    Standard-500 mit `{detail}` durchschlagen und den Fehler-Contract brechen. Der
    registrierte Exception-Handler bildet diese Exception contract-konform auf
    503 `{code, message}` ab (NF-01: nie GRUEN, auch nicht bei Startup-Fehlern).
    """


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


def _service_unavailable(message: str) -> JSONResponse:
    """Baut die 503-Antwort im Contract-Fehlerformat `Error {code, message}`.

    Bewusst NICHT `HTTPException(detail=...)`: das liefert `{"detail": ...}` und
    bricht damit die eingefrorene Naht (Contract verlangt `{code, message}`).
    Die Nachricht bleibt generisch (keine internen Details/Secrets, RB-01/Contract D).
    """
    return JSONResponse(
        status_code=503,
        content=Error(code=_SERVICE_UNAVAILABLE_CODE, message=message).model_dump(),
    )


async def run_scheduler(runtime: Runtime, interval_s: float) -> None:
    """Periodische Poll-/Bewertungs-Schleife (TODO DTB-64: ausbauen/haerten).

    Fail-safe: ein Fehler in einem Zyklus beendet die Schleife NICHT; der naechste
    Zyklus versucht es erneut. Serve-Zeit-NF-01 (build_assessment_current) faengt
    derweil veraltete Daten ab (nie GRUEN).
    """
    logger.info("DTB-64: Scheduler gestartet (Intervall %.0fs).", interval_s)
    while True:
        try:
            # poller.poll() ist blockierend (httpx.get) -> in einen Thread auslagern,
            # damit der Event-Loop frei bleibt.
            reading = await asyncio.to_thread(runtime.poller.poll)
            now = datetime.now(UTC)
            await asyncio.to_thread(runtime.service.assess_reading, reading, now)
        except RepositoryError as exc:
            logger.error("Bewertungszyklus fehlgeschlagen (fail-safe, weiter): %s", exc)
        except ValueError:
            # Invariantenbruch / Programmierfehler (z. B. DTB-28: Reading ohne id auf
            # dem Gutfall-Pfad) — KEIN transienter Betriebsfehler. CRITICAL, damit Ops
            # den Unterschied zu erwartbaren Fehlern sieht; der Scheduler laeuft
            # fail-safe weiter (NF-01), aber das ist ein Bug, kein Datenzustand.
            logger.critical(
                "Invariantenbruch im Bewertungszyklus (Bug, nicht transient) — "
                "Zyklus uebersprungen, bitte pruefen.",
                exc_info=True,
            )
        except Exception:  # noqa: BLE001 - Scheduler darf nie sterben (NF-01)
            logger.exception("Unerwarteter Fehler im Scheduler (fail-safe, weiter).")
        await asyncio.sleep(interval_s)


def _scheduler_enabled() -> bool:
    return os.environ.get("G2_ENABLE_SCHEDULER", "").strip().lower() in {"1", "true", "yes", "on"}


def _poll_interval_s() -> float:
    # TODO DTB-64: aus thresholds (betrieb.poll_interval_s) statt Env/Default.
    return float(os.environ.get("G2_POLL_INTERVAL_S", _DEFAULT_POLL_INTERVAL_S))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startet/stoppt den Hintergrund-Scheduler und haengt den Runtime-Graph an app.state."""
    runtime = build_runtime()
    app.state.runtime = runtime
    task: asyncio.Task[None] | None = None
    if _scheduler_enabled():
        task = asyncio.create_task(run_scheduler(runtime, _poll_interval_s()))
    else:
        logger.info(
            "DTB-64: Scheduler deaktiviert (G2_ENABLE_SCHEDULER nicht gesetzt) — "
            "TODO: nach DB-/G1-Verdrahtung aktivieren."
        )
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="Alarmsystem-Backend G2 — Vereisungserkennung ANR",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RuntimeNotReadyError)
async def _runtime_not_ready_handler(
    _request: Request, exc: RuntimeNotReadyError
) -> JSONResponse:
    """Fehlt der Runtime-Graph, contract-konform als 503 melden (nie rohes 500/{detail})."""
    logger.error("Runtime nicht verfuegbar: %s", exc)
    return _service_unavailable("G2 momentan nicht lieferfaehig.")


@app.get("/v1/health")
def health() -> dict[str, str]:
    """Liveness-Check (P0.3): bestätigt, dass der Server erreichbar ist.

    TODO DTB-64: auf Pydantic `Health` + 503-Pfad heben (Contract-Treue).
    """
    return {"status": "ok"}


@app.get(
    "/v1/assessment/current",
    tags=["Assessment"],
    response_model=AssessmentCurrent,
    responses={
        503: {
            "model": Error,
            "description": (
                "G2 nicht lieferfaehig (noch keine Bewertung / interner Ausfall). "
                "NICHT fuer Stale — Stale ist 200 + is_stale=true."
            ),
        }
    },
)
def assessment_current(
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> AssessmentCurrent | JSONResponse:
    """Aktuelle Vereisungsbewertung fuer G3 (Contract v1, E-36, DTB-43).

    Fail-safe NF-01 in zwei bewusst getrennten Klassen (Contract-konform):

    - **Daten veraltet (stale) ODER Sensor `fault`** -> HTTP 200 mit
      `risk_level=unknown` (nie GRUEN). `build_assessment_current` erzwingt das
      zur Serve-Zeit und nullt die Messwerte. Kein Fehler (Contract: 503 NICHT
      fuer Stale).
    - **G2 nicht lieferfaehig** (noch keine Bewertung/Reading ODER DB-Ausfall) ->
      HTTP 503 mit `Error {code, message}`.

    Warum 503 (statt 200/unknown) beim DB-Ausfall: der Wire-Response setzt
    `measured_at` auf 200 zwingend voraus; bei einem DB-Lesefehler liegt gar kein
    Reading vor, ein 200/unknown waere also nicht contract-darstellbar. Die
    Jira-DoD (DTB-43) nennt fuer den DB-Ausfall woertlich `unknown`; der
    eingefrorene Contract (Source of Truth) bildet einen internen Ausfall auf 503
    ab und gewinnt -> 503 (begruendet im Lucas-Entscheidungslog).
    """
    try:
        assessment = runtime.assessment_repo.get_latest()
        readings = runtime.reading_repo.get_latest(_SENSOR_ID, limit=1)
    except RepositoryError as exc:
        # DB-Ausfall: Detail server-seitig loggen, nach aussen nur generisch (Contract D).
        logger.error("assessment/current: Persistenz nicht verfuegbar: %s", exc)
        return _service_unavailable("G2 momentan nicht lieferfaehig.")

    reading = readings[0] if readings else None
    if assessment is None or reading is None:
        # Noch kein vollstaendiger Snapshot (frischer Start / Retention) -> nicht lieferfaehig.
        return _service_unavailable("Noch keine Bewertung verfuegbar.")

    try:
        return build_assessment_current(
            assessment,
            reading,
            datetime.now(UTC),
            runtime.thresholds.datenqualitaet.stale_timeout_s,
        )
    except Exception:  # noqa: BLE001 - Serving darf nie als 500/{detail} brechen (NF-01/Contract)
        # Unerwarteter Aufbereitungsfehler (z. B. fehlkonfigurierter stale_timeout_s ->
        # is_stale-ValueError, oder kuenftig ein zu langer explanation-Text). Contract-
        # konform als 503 melden statt rohem 500 mit {detail}; Detail nur server-seitig.
        logger.exception("assessment/current: Bewertung konnte nicht aufbereitet werden")
        return _service_unavailable("G2 momentan nicht lieferfaehig.")
