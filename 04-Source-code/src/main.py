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

Offene TODOs fuer den Ausbau (heute Abend):
  1. GET /v1/assessment/current (DTB-43): liest runtime.assessment_repo.get_latest()
     + runtime.reading_repo.get_latest(sensor_id), 503 wenn keines, sonst
     build_assessment_current(...). Beispiel unten.
  2. poll_interval_s aus Config laden (neues Feld betrieb.poll_interval_s, P0-a)
     statt aus Env/Default.
  3. GET /v1/health auf Pydantic `Health` + 503-Pfad heben (Contract-Treue).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI

from src.assessment import AssessmentService
from src.config.loader import Thresholds, load_thresholds
from src.forecast.bridge import compute_forecast_for_cycle
from src.ingest.poller import Poller
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


async def run_scheduler(runtime: Runtime, interval_s: float) -> None:
    """Periodische Poll-/Bewertungs-Schleife.

    Poller holt Snapshot von G1, Prognose-Producer liest die T_s-Historie
    (DTB-33/FA-06), AssessmentService bewertet + persistiert. Fail-safe: ein
    Fehler in einem Zyklus beendet die Schleife NICHT; der naechste Zyklus
    versucht es erneut. Serve-Zeit-NF-01 (build_assessment_current) faengt
    derweil veraltete Daten ab (nie GRUEN).

    Offene DTB-64-Ausbauten: GET /v1/assessment/current, poll_interval_s aus
    Config statt Env, Pydantic-Health-Response.
    """
    logger.info("DTB-64: Scheduler gestartet (Intervall %.0fs).", interval_s)
    while True:
        try:
            # poller.poll() ist blockierend (httpx.get) -> in einen Thread auslagern,
            # damit der Event-Loop frei bleibt.
            # now VOR dem Poll: haelt assessed_at nahe an measured_at (Audit-Konsistenz)
            # und definiert das 30-min-Prognosefenster ab Zyklusbeginn.
            now = datetime.now(UTC)
            reading = await asyncio.to_thread(runtime.poller.poll)
            # DTB-33 (FA-06): 30-min-T_s-Prognose aus der Historie -> GELB-Vorwarnung.
            # Bruecke liest die Zeitreihe; Fail-safe: None bei fehlendem Reading/DB-Fehler.
            forecast = await asyncio.to_thread(
                compute_forecast_for_cycle,
                reading,
                runtime.reading_repo,
                runtime.thresholds.prognose,
                now,
            )
            await asyncio.to_thread(runtime.service.assess_reading, reading, now, forecast)
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


@app.get("/v1/health")
def health() -> dict[str, str]:
    """Liveness-Check (P0.3): bestätigt, dass der Server erreichbar ist.

    TODO DTB-64: auf Pydantic `Health` + 503-Pfad heben (Contract-Treue).
    """
    return {"status": "ok"}


# TODO DTB-64 / DTB-43 — GET /v1/assessment/current. Geruest (auskommentiert, damit
# der Stub ohne DB lauffaehig bleibt). build_assessment_current + Repos sind fertig:
#
# from fastapi import HTTPException, Request
# from src.assessment import build_assessment_current
# from src.model.schemas import AssessmentCurrent
#
# _SENSOR_ID = "anr-rwy-01"  # FIXME vor Aktivierung: aus Config laden (F24/Geo) — NICHT hardcoden!
#
# @app.get("/v1/assessment/current", response_model=AssessmentCurrent)
# def assessment_current(request: Request) -> AssessmentCurrent:
#     runtime: Runtime = request.app.state.runtime
#     try:
#         assessment = runtime.assessment_repo.get_latest()
#         readings = runtime.reading_repo.get_latest(_SENSOR_ID, limit=1)
#     except RepositoryError as exc:
#         logger.error("assessment/current: Persistenz nicht verfuegbar: %s", exc)
#         raise HTTPException(status_code=503, detail="G2 nicht lieferfaehig") from exc
#     reading = readings[0] if readings else None
#     if assessment is None or reading is None:
#         raise HTTPException(status_code=503, detail="Noch keine Daten")
#     return build_assessment_current(
#         assessment, reading, datetime.now(UTC),
#         runtime.thresholds.datenqualitaet.stale_timeout_s,
#     )
