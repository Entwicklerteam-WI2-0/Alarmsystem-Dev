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
  - poll_interval_s aus Config geladen (betrieb.poll_interval_s, P0-a/DTB-27).
  - Alarm-Generierung im Bewertungszyklus verdrahtet (run_assessment_cycle, DTB-27).

Offene TODOs fuer den Ausbau:
  - GET /v1/health auf Pydantic `Health` + 503-Pfad heben (Contract-Treue).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator, AuditError
from src.api.broadcaster import AlarmBroadcaster
from src.api.exceptions import RuntimeNotReadyError
from src.api.responses import NO_STORE_HEADERS, service_unavailable
from src.api.runtime import Runtime, get_runtime
from src.api.v1 import router as v1_router
from src.assessment import AssessmentService, build_assessment_current
from src.config.loader import load_thresholds
from src.ingest.poller import Poller
from src.model.schemas import Alarm, AssessmentCurrent, Error, Reading
from src.storage import (
    MySqlAssessmentRepository,
    MySqlAuditRepository,
    ReadingRepository,
    RepositoryError,
)
from src.storage.alarm_repository import MySqlAlarmRepository

logger = logging.getLogger(__name__)

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
    # DTB-27: Alarm-Generierung als Konsument der Bewertung. AlarmHysterese ist pro Sensor
    # zustandsbehaftet (On-Delay) -> gehört in den langlebigen DI-Graph (eine Instanz je
    # laufende Instanz; aktuell genau ein Sensor). Audit-Log wird mit dem Service geteilt.
    alarm_generator = AlarmGenerator(
        AlarmHysterese(thresholds.hysterese), MySqlAlarmRepository(), audit_repo
    )
    # DTB-61: ein Broadcaster pro laufende Instanz — geteilt zwischen run_scheduler (Producer)
    # und GET /v1/alarms/stream (Consumer). Haelt nur In-Memory-Abos, kontaktiert nichts.
    alarm_broadcaster = AlarmBroadcaster()
    return Runtime(
        thresholds=thresholds,
        reading_repo=reading_repo,
        assessment_repo=assessment_repo,
        audit_repo=audit_repo,
        poller=poller,
        service=service,
        alarm_generator=alarm_generator,
        alarm_broadcaster=alarm_broadcaster,
    )


def run_assessment_cycle(
    service: AssessmentService,
    alarm_generator: AlarmGenerator,
    reading: Reading | None,
    now: datetime,
) -> Alarm | None:
    """Ein vollständiger Zyklus: Bewertung (DTB-64) -> Alarm-Generierung (DTB-27).

    `assess_reading` erzwingt das Laufzeit-NF-01 (stale/fault/keine Daten -> unknown) und
    liefert das persistierte Assessment; dessen `risk_level` speist die Alarm-Generierung.
    Bei `unknown` löst der Generator keinen Alarm aus und die On-Delay-Hysterese friert ein —
    die in DTB-27 dokumentierte Vorbedingung (Stale -> UNKNOWN, nicht GELB) erfüllt DTB-64 hier.

    Returns:
        Den ausgelösten `Alarm` (mit id), wenn dieser Zyklus einen Alarm erzeugt hat; sonst
        `None`. `run_scheduler` reicht ihn an den `AlarmBroadcaster` weiter (DTB-61, Live-Push).

    Bewusst KEIN eigenes try/except: Persistenz-/Audit-Fehler propagieren in die Fail-safe-
    Schleife des Schedulers (NF-01: ein Zyklus-Fehler beendet den Betrieb nicht).
    """
    assessment = service.assess_reading(reading, now)
    if assessment.id is None:  # pragma: no cover - defensiver Invarianten-Guard
        # assess_reading garantiert eine persistierte id; fehlt sie, ist die Invariante
        # verletzt -> laut scheitern (kein assert, -O-fest), statt stumm einen Alarm ohne
        # Assessment-Bezug zu erzeugen. Der Scheduler protokolliert das als Bug (CRITICAL).
        raise ValueError(
            "assessment.id ist None trotz Persistenz (assess_reading-Invariante verletzt)"
        )
    return alarm_generator.verarbeite(assessment.risk_level, assessment.id, now)


async def run_scheduler(runtime: Runtime, interval_s: float) -> None:
    """Periodische Poll-/Bewertungs-Schleife (TODO DTB-64: ausbauen/haerten).

    Fail-safe: ein Fehler in einem Zyklus beendet die Schleife NICHT; der naechste
    Zyklus versucht es erneut. Serve-Zeit-NF-01 (build_assessment_current) faengt
    derweil veraltete Daten ab (nie GRUEN).
    """
    logger.info("DTB-64: Scheduler gestartet (Intervall %.0fs).", interval_s)
    last_now: datetime | None = None
    while True:
        try:
            # poller.poll() ist blockierend (httpx.get) -> in einen Thread auslagern,
            # damit der Event-Loop frei bleibt.
            reading = await asyncio.to_thread(runtime.poller.poll)
            now = datetime.now(UTC)
            # Monotonie erzwingen (Hysterese-Vorbedingung): eine NTP-Rueckwaertskorrektur der
            # Wall-Clock darf die On-Delay-Akkumulation nicht zuruecksetzen (sonst einmaliger
            # Under-Alarm). Nicht-fallende Zeit an die Engines weiterreichen; Clock-Skew fuer
            # Ops sichtbar machen (anhaltender Rueckwaerts-Offset friert die Zeit kurz ein).
            if last_now is not None and now < last_now:
                logger.warning(
                    "Wall-Clock-Rueckwaertssprung (%.1fs) - Zeit geklemmt (Clock-Skew?).",
                    (last_now - now).total_seconds(),
                )
                now = last_now
            last_now = now
            raised = await asyncio.to_thread(
                run_assessment_cycle,
                runtime.service,
                runtime.alarm_generator,
                reading,
                now,
            )
            if raised is not None:
                # DTB-61: Live-Push BEWUSST auf dem Event-Loop (nicht im to_thread-Worker) ->
                # der Broadcaster greift direkt auf asyncio.Queues zu, das ist nur loop-seitig
                # safe (kein cross-thread put). publish ist best-effort und wirft nie (NF-01).
                # Hinweis: Auf dem AuditError-Pfad (Alarm gespeichert, Audit fehlgeschlagen)
                # wird hier NICHT gepusht (verarbeite wirft, kein Return) -> G3 bekommt den
                # Alarm ueber den Resync GET /v1/alarms (DTB-31, E-37).
                runtime.alarm_broadcaster.publish(raised)
        except AuditError as exc:
            # Alarm IST gespeichert + Engine aktiv (KEIN Re-Arm), aber OHNE Audit-Trail -> ERROR
            # (nicht WARNING): ein persistierter Alarm ohne Audit-Eintrag ist eine Luecke in der
            # Nachvollziehbarkeit (NF-09). alarm_id mitloggen, damit Ops das vom verschluckten
            # Alarm (reiner RepositoryError, bei dem ein Re-Arm stattfand) unterscheiden kann.
            logger.error(
                "Alarm %s gespeichert, aber Audit-Eintrag fehlgeschlagen (kein Re-Arm): %s",
                exc.alarm_id,
                exc,
            )
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


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startet/stoppt den Hintergrund-Scheduler und haengt den Runtime-Graph an app.state."""
    runtime = build_runtime()
    app.state.runtime = runtime
    task: asyncio.Task[None] | None = None
    if _scheduler_enabled():
        task = asyncio.create_task(
            run_scheduler(runtime, runtime.thresholds.betrieb.poll_interval_s)
        )
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

# Versionierte /v1-Endpoints (Serving zu G3), z. B. GET /v1/thresholds (DTB-62).
app.include_router(v1_router)


@app.exception_handler(RuntimeNotReadyError)
async def _runtime_not_ready_handler(_request: Request, exc: RuntimeNotReadyError) -> JSONResponse:
    """Fehlt der Runtime-Graph, contract-konform als 503 melden (nie rohes 500/{detail})."""
    logger.error("Runtime nicht verfuegbar: %s", exc)
    return service_unavailable("G2 momentan nicht lieferfaehig.")


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
    response: Response,
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
    # no-store auch auf dem 200-Pfad: ein gecachter Momentan-Zustand (stale/unknown/
    # green) waere ein veraltetes Sicherheitssignal (NF-01). Die direkt zurueckgegebenen
    # 503-JSONResponses tragen den Header selbst (service_unavailable).
    response.headers.update(NO_STORE_HEADERS)
    try:
        assessment = runtime.assessment_repo.get_latest()
        readings = runtime.reading_repo.get_latest(_SENSOR_ID, limit=1)
    except RepositoryError as exc:
        # DB-Ausfall: Detail server-seitig loggen, nach aussen nur generisch (Contract D).
        logger.error("assessment/current: Persistenz nicht verfuegbar: %s", exc)
        return service_unavailable("G2 momentan nicht lieferfaehig.")

    reading = readings[0] if readings else None
    if assessment is None or reading is None:
        # Noch kein vollstaendiger Snapshot (frischer Start / Retention) -> nicht lieferfaehig.
        return service_unavailable("Noch keine Bewertung verfuegbar.")

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
        return service_unavailable("G2 momentan nicht lieferfaehig.")
