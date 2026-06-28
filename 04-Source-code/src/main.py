"""FastAPI-Einstiegspunkt des G2-Backends (Vereisungserkennung ANR).

Laufzeit-Verdrahtung (DTB-64) der T0-Slice — Poller, Bewertung, Persistenz,
Audit und Serving sind hier zu einem laufenden Dienst zusammengefuehrt:

  Poller --(poll alle poll_interval_s)--> AssessmentService.assess_reading
        --> AssessmentRepository.save + AuditRepository.append
  GET /v1/assessment/current --> build_assessment_current(latest_assessment, latest_reading)

Der Scheduler ist bewusst hinter `G2_ENABLE_SCHEDULER` gated (Default AUS), damit
`uvicorn`/Tests ohne DB/G1 nicht crashen. Zum Scharfschalten: Env setzen +
DB-/G1-Variablen bereitstellen (s. database.py / G1_BASE_URL).

Endpoints (Contract v1):
  - GET /v1/health (P0.3): Liveness-Probe -> 200 Health{status:"ok"}, sonst 503
    (Error{code,message}) solange der Runtime-/DI-Graph fehlt (Startup/Ausfall).
  - GET /v1/assessment/current (DTB-43): liest runtime.assessment_repo.get_latest()
    + runtime.reading_repo.get_latest(sensor_id); 503 (Error{code,message}) bei
    DB-Ausfall / keinen Daten, sonst build_assessment_current(...) mit Serve-Zeit-NF-01.

poll_interval_s kommt aus Config (betrieb.poll_interval_s, P0-a/DTB-27); die
Alarm-Generierung ist im Bewertungszyklus verdrahtet (run_assessment_cycle, DTB-27).
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
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator, AuditError
from src.api.broadcaster import AlarmBroadcaster
from src.api.exceptions import (
    ApiKeyNotConfiguredError,
    AuthenticationError,
    RuntimeNotReadyError,
)
from src.api.responses import (
    NO_STORE_HEADERS,
    service_unavailable,
    unauthorized,
)
from src.api.runtime import Runtime, get_runtime
from src.api.v1 import router as v1_router
from src.assessment import AssessmentService, build_assessment_current
from src.config.constants import DEFAULT_SENSOR_ID
from src.config.loader import ConfigError, Thresholds, load_thresholds, parse_thresholds
from src.forecast.bridge import compute_forecast_for_cycle
from src.ingest.poller import Poller
from src.model.schemas import Alarm, AssessmentCurrent, Error, Health, Reading
from src.storage import (
    MySqlAssessmentRepository,
    MySqlAuditRepository,
    MySqlThresholdSetRepository,
    ReadingRepository,
    RepositoryError,
    ThresholdSetRepository,
)
from src.storage.acknowledgement_repository import MySqlAcknowledgementRepository
from src.storage.alarm_repository import MySqlAlarmRepository

logger = logging.getLogger(__name__)

# Bewusster Default: http:// im abgeschlossenen Projekt-/Intranet (G1 ist ein
# Prototyp ohne TLS). Fuer realen Betrieb HTTPS NICHT hier hart erzwingen — ein
# https://-Default wuerde die Verbindung zu einem HTTP-only-G1 brechen (eingefrorene
# Naht). Stattdessen pro Umgebung per Env umstellen: G1_BASE_URL=https://g1-sensorik.local
# (dokumentiert in .env.example). Architektenentscheidung, falls HTTPS-Default + HTTP-Opt-in
# gewuenscht wird.
_DEFAULT_G1_BASE_URL = "http://g1-sensorik.local"


# CORS (C1, Vorbereitung G3-Browser-Integration / DTB-23): G3 ist ein Browser-Frontend
# von ANDERER Origin (eigener Host/Port). Ohne CORS-Header blockt der Browser per
# Same-Origin-Policy JEDEN Call von G3 -> Server-zu-Server und die pytest-Suite sind davon
# unberuehrt, die echte UI aber nicht. Bewusster Default "*" fuer den abgeschlossenen
# Prototyp/Intranet (analog zum http-Default von G1): pro Umgebung per Env einschraenken,
# z. B. G2_CORS_ORIGINS="http://devpi.local:3000" (dokumentiert in .env.example).
# allow_credentials bleibt False -> mit "*" kompatibel und ausreichend, da Auth (DTB-63)
# ueber den Authorization-Header laeuft, nicht ueber Cookies.
_DEFAULT_CORS_ORIGINS = "*"


def build_runtime() -> Runtime:
    """Baut den DI-Graph (Repos verbinden erst pro Query, kein DB-Zwang beim Start).

    Aktive Schwellen = zuletzt gespeicherter `threshold_set` (DB, DTB-63-Reload-
    Semantik); ist die Tabelle leer oder die DB beim Start nicht erreichbar, wird die
    JSON-Seed-Config verwendet (`_load_active_thresholds`). So bleibt der Stub ohne DB
    lauffaehig (der Scheduler ist ohnehin per Default aus).
    """
    threshold_set_repo = MySqlThresholdSetRepository()
    thresholds = _load_active_thresholds(threshold_set_repo)
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
    # DTB-24: Quittierungs-Repo fuer POST /v1/alarms/{id}/ack (verbindet State-Wechsel +
    # acknowledgement-Eintrag + Audit atomar). Wie die uebrigen MySql-Repos: verbindet erst pro
    # Query, kontaktiert beim Bauen des Graphen keine DB.
    ack_repo = MySqlAcknowledgementRepository()
    return Runtime(
        thresholds=thresholds,
        reading_repo=reading_repo,
        assessment_repo=assessment_repo,
        audit_repo=audit_repo,
        threshold_set_repo=threshold_set_repo,
        poller=poller,
        service=service,
        alarm_generator=alarm_generator,
        alarm_broadcaster=alarm_broadcaster,
        ack_repo=ack_repo,
    )


def _load_active_thresholds(threshold_set_repo: ThresholdSetRepository) -> Thresholds:
    """Aktive Schwellen = zuletzt gespeicherter `threshold_set`, sonst JSON-Seed.

    Reload-Semantik (DTB-63): ein per POST /v1/thresholds gespeicherter Satz wird beim
    naechsten Start aktiv. Faellt die DB aus oder ist die Tabelle leer, wird die
    JSON-Seed-Config geladen (fail-safe: lieber die committete Basiskalibrierung als
    gar keine Schwellen). Fehler werden laut geloggt (kein stilles Maskieren).
    """
    try:
        latest = threshold_set_repo.get_latest()
    except RepositoryError as exc:
        logger.warning(
            "threshold_set nicht lesbar (%s) -> JSON-Seed-Config (config/thresholds.json).", exc
        )
        return load_thresholds()
    if latest is None:
        logger.info("Kein threshold_set in der DB -> JSON-Seed-Config (config/thresholds.json).")
        return load_thresholds()
    try:
        return parse_thresholds(latest.params)
    except ConfigError as exc:
        logger.error(
            "Gespeicherter threshold_set (id=%s) ist ungueltig (%s) -> JSON-Seed-Config.",
            latest.id,
            exc,
        )
        return load_thresholds()


def run_assessment_cycle(
    service: AssessmentService,
    alarm_generator: AlarmGenerator,
    reading: Reading | None,
    now: datetime,
    forecast_surface_temp_c: float | None = None,
) -> Alarm | None:
    """Ein vollständiger Zyklus: Bewertung (DTB-64) -> Alarm-Generierung (DTB-27).

    `assess_reading` erzwingt das Laufzeit-NF-01 (stale/fault/keine Daten -> unknown) und
    liefert das persistierte Assessment; dessen `risk_level` speist die Alarm-Generierung.
    Bei `unknown` löst der Generator keinen Alarm aus und die On-Delay-Hysterese friert ein —
    die in DTB-27 dokumentierte Vorbedingung (Stale -> UNKNOWN, nicht GELB) erfüllt DTB-64 hier.

    `forecast_surface_temp_c` ist die optionale 30-min-T_s-Prognose (DTB-33/FA-06); sie wird
    an die Bewertung durchgereicht und speist die GELB-Vorwarnung. None (Default) = keine
    Prognose verfügbar (Fail-safe) -> Bewertung allein aus dem aktuellen Reading.

    Returns:
        Den ausgelösten `Alarm` (mit id), wenn dieser Zyklus einen Alarm erzeugt hat; sonst
        `None`. `run_scheduler` reicht ihn an den `AlarmBroadcaster` weiter (DTB-61, Live-Push).

    Bewusst KEIN eigenes try/except: Persistenz-/Audit-Fehler propagieren in die Fail-safe-
    Schleife des Schedulers (NF-01: ein Zyklus-Fehler beendet den Betrieb nicht).
    """
    # Keyword fuer forecast_surface_temp_c: `now` und der Prognosewert stehen beide
    # float|None-nah nebeneinander -> benannt halten, damit eine Signaturreihenfolgen-
    # aenderung nicht still die Argumente vertauscht.
    assessment = service.assess_reading(
        reading, now, forecast_surface_temp_c=forecast_surface_temp_c
    )
    if assessment.id is None:  # pragma: no cover - defensiver Invarianten-Guard
        # assess_reading garantiert eine persistierte id; fehlt sie, ist die Invariante
        # verletzt -> laut scheitern (kein assert, -O-fest), statt stumm einen Alarm ohne
        # Assessment-Bezug zu erzeugen. Der Scheduler protokolliert das als Bug (CRITICAL).
        raise ValueError(
            "assessment.id ist None trotz Persistenz (assess_reading-Invariante verletzt)"
        )
    return alarm_generator.verarbeite(assessment.risk_level, assessment.id, now)


async def run_scheduler(runtime: Runtime, interval_s: float) -> None:
    """Periodische Poll-/Bewertungs-Schleife (Scheduler-Kern der T0-Slice, DTB-64).

    Poller holt Snapshot von G1, Prognose-Producer liest die T_s-Historie
    (DTB-33/FA-06), AssessmentService bewertet + persistiert. Fail-safe: ein
    Fehler in einem Zyklus beendet die Schleife NICHT; der naechste Zyklus
    versucht es erneut. Serve-Zeit-NF-01 (build_assessment_current) faengt
    derweil veraltete Daten ab (nie GRUEN).
    """
    logger.info("DTB-64: Scheduler gestartet (Intervall %.0fs).", interval_s)
    last_now: datetime | None = None
    while True:
        try:
            # poller.poll() ist blockierend (httpx.get) -> in einen Thread auslagern,
            # damit der Event-Loop frei bleibt.
            # now VOR dem Poll: haelt assessed_at nahe an measured_at (Audit-Konsistenz)
            # und definiert das 30-min-Prognosefenster ab Zyklusbeginn.
            now = datetime.now(UTC)
            reading = await asyncio.to_thread(runtime.poller.poll)
            # Monotonie erzwingen (Hysterese-Vorbedingung): eine NTP-Rueckwaertskorrektur der
            # Wall-Clock darf die On-Delay-Akkumulation nicht zuruecksetzen (sonst einmaliger
            # Under-Alarm). Nicht-fallende Zeit an die Engines weiterreichen; Clock-Skew fuer
            # Ops sichtbar machen (anhaltender Rueckwaerts-Offset friert die Zeit kurz ein).
            # Das geklemmte `now` ist auch die gemeinsame Zeitbasis fuer Prognose UND Bewertung.
            if last_now is not None and now < last_now:
                logger.warning(
                    "Wall-Clock-Rueckwaertssprung (%.1fs) - Zeit geklemmt (Clock-Skew?).",
                    (last_now - now).total_seconds(),
                )
                now = last_now
            last_now = now
            # DTB-33 (FA-06): 30-min-T_s-Prognose aus der Historie -> GELB-Vorwarnung.
            # Bruecke liest die Zeitreihe; Fail-safe: None bei fehlendem Reading/DB-Fehler.
            # Clock-Skew-Implikation: `now` wird VOR dem Poll gesetzt. Laeuft die G1-Uhr G2 vor,
            # liegt das soeben gepollte measured_at > now und faellt aus dem Trendfenster
            # (trend.py verwirft `> now`). Das ist fail-safe (None senkt nie ab), kann aber bei
            # duenner Datenlage die Prognose still degradieren. Bewusst NICHT `now = max(now,
            # measured_at)`: das braeche die oben erzwungene Monotonie-Invariante der Hysterese.
            # Prognose-Isolation (NF-01): die 30-min-Vorwarnung ist eine NICHT-kritische
            # Hilfsfunktion. compute_forecast_for_cycle ist bereits fail-safe (None bei
            # RepositoryError/fehlendem Reading), aber ein hier nicht erwarteter Fehler
            # (kuenftige Regression im Producer, ungefangener DB-Edge-Case) wuerde sonst ins
            # aeussere except propagieren und run_assessment_cycle in DIESEM Tick auslassen —
            # eine Hilfsfunktion duerfte dann den sicherheitskritischen Bewertungspfad
            # blockieren. Darum eigen kapseln: loggen (sichtbar, kein stilles Schlucken) ->
            # forecast=None -> Bewertung laeuft unbedingt weiter (allein auf dem Ist-Reading).
            try:
                forecast = await asyncio.to_thread(
                    compute_forecast_for_cycle,
                    reading,
                    runtime.reading_repo,
                    runtime.thresholds.prognose,
                    now,
                )
            except Exception:  # noqa: BLE001 - Prognose-Fehler darf Bewertung nie blockieren (NF-01)
                # Fängt auch den ValueError aus bridge.py (naives `now`) ab, der
                # laut Docstring sichtbar werden soll. Durch logger.exception bleibt
                # er sichtbar; die Bewertung läuft unbedingt weiter (NF-01).
                logger.exception("Prognose fehlgeschlagen (fail-safe, forecast=None).")
                forecast = None
            raised = await asyncio.to_thread(
                run_assessment_cycle,
                runtime.service,
                runtime.alarm_generator,
                reading,
                now,
                # Keyword (nicht 5. Positionsarg): konsistent zum inneren assess_reading-Aufruf,
                # damit eine Signaturreihenfolgen-Aenderung die Argumente nicht still vertauscht.
                forecast_surface_temp_c=forecast,
            )
            if raised is not None:
                # DTB-61: Live-Push BEWUSST auf dem Event-Loop (nicht im to_thread-Worker) ->
                # der Broadcaster greift direkt auf asyncio.Queues zu, das ist nur loop-seitig
                # safe (kein cross-thread put). publish ist best-effort und wirft nie (NF-01).
                # (Der AuditError-Pfad pusht separat im except unten -> SSE bleibt vollstaendig,
                # G3 muss nicht auf den GET /v1/alarms-Resync warten; NF-01 vor NF-09.)
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
            # NF-01 vor NF-09: der Alarm IST persistiert -> trotz der (oben geloggten) Audit-
            # Luecke live an G3 pushen, damit der SSE-Stream vollstaendig bleibt und G3 nicht auf
            # den GET /v1/alarms-Resync warten muss. publish ist best-effort und wirft nie (NF-01).
            runtime.alarm_broadcaster.publish(exc.alarm)
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


def _cors_origins() -> list[str]:
    """Erlaubte CORS-Origins aus Env (komma-separiert); Default/leer/"*" -> ["*"].

    Prototyp/Intranet. Hinweis (Deployment): wird einmalig beim App-Start (Modulimport,
    add_middleware) gelesen -> Aenderung von G2_CORS_ORIGINS wirkt erst nach App-Neustart,
    nicht per systemd-Reload.
    """
    raw = os.environ.get("G2_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).strip()
    # Leerer String (z. B. `G2_CORS_ORIGINS=` in der .env) zaehlt wie "nicht gesetzt":
    # auf den offenen Default zurueckfallen, statt CORS still komplett zu sperren
    # (ein versehentlich leerer Wert ist wahrscheinlicher als bewusstes Block-all).
    if not raw:
        return ["*"]
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    # "*" dominiert: taucht der Wildcard irgendwo in der Liste auf (auch Mischform wie
    # "*,http://x"), gilt er allein -> ["*"]. Vermeidet eine ueberraschende gemischte
    # allow_origins-Liste.
    if "*" in origins:
        return ["*"]
    return origins


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

# CORS (C1): erlaubt G3s Browser-Frontend (andere Origin) den Zugriff. Methoden bewusst
# auf die Contract-Verben begrenzt (GET = lesen/SSE, POST = /v1/alarms/{id}/ack).
# Origins/Default siehe _cors_origins / _DEFAULT_CORS_ORIGINS oben.
# expose_headers bleibt Default (leer): G3 liest nur CORS-safelisted Response-Header (u. a.
# Cache-Control) — fuer den aktuellen Contract ausreichend. Muss G3 spaeter einen Custom-Header
# lesen (z. B. X-Request-Id), hier expose_headers=[...] ergaenzen.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Versionierte /v1-Endpoints (Serving zu G3), z. B. GET /v1/thresholds (DTB-62).
app.include_router(v1_router)


@app.exception_handler(RuntimeNotReadyError)
async def _runtime_not_ready_handler(_request: Request, exc: RuntimeNotReadyError) -> JSONResponse:
    """Fehlt der Runtime-Graph, contract-konform als 503 melden (nie rohes 500/{detail})."""
    logger.error("Runtime nicht verfuegbar: %s", exc)
    return service_unavailable("G2 momentan nicht lieferfaehig.")


@app.exception_handler(AuthenticationError)
async def _authentication_error_handler(
    _request: Request, exc: AuthenticationError
) -> JSONResponse:
    """Fehlender/ungueltiger API-Key -> contract-konform 401 (nie 403/{detail})."""
    logger.warning("Authentifizierung fehlgeschlagen: %s", exc)
    return unauthorized("Ungueltiger oder fehlender API-Key.")


@app.exception_handler(ApiKeyNotConfiguredError)
async def _api_key_not_configured_handler(
    _request: Request, exc: ApiKeyNotConfiguredError
) -> JSONResponse:
    """G2_API_KEY nicht gesetzt -> Schreibzugriff fail-safe-closed als 503 melden."""
    logger.error("Schreibzugriff nicht konfiguriert: %s", exc)
    return service_unavailable("Schreibzugriff nicht konfiguriert.")


@app.exception_handler(RequestValidationError)
async def _request_validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """FastAPI-Validierungsfehler contract-konform abbilden.

    Query-/Pfad-/Header-Fehler sind Request-Fehler -> 400 `Error {code, message}`.
    Body-Schema-Fehler (POST/PUT/PATCH) bleiben 422, weil der Contract `422` explizit
    fuer Body-Validierung reserviert (API_FROZEN_v1.md §2D). Betrifft auch den ack-Body
    (DTB-24, POST /v1/alarms/{id}/ack); ein nicht-numerischer Pfad-`id` faellt als 400.
    """
    errors = exc.errors()
    has_body_error = any(err.get("loc", [None])[0] == "body" for err in errors)
    message = "; ".join(
        f"{' -> '.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in errors
    )
    # Error.message ist auf max_length=512 begrenzt (schemas.py). Bei mehreren/langen
    # Validierungsfehlern wuerde Error(...) sonst SELBST eine ValidationError werfen und
    # so einen unkontrollierten Folge-500 IM Handler ausloesen (vgl. Kommentar v1.py).
    # Defensiv kappen -> der Handler liefert immer ein gueltiges Error{code, message}.
    message = message[:512]
    if has_body_error:
        return JSONResponse(
            status_code=422,
            # Contract-konformer 422-Code: openapi.yaml fuehrt UNPROCESSABLE_ENTITY (identisch zur
            # Konstante UNPROCESSABLE_ENTITY_CODE in api/responses.py, die der Helper
            # unprocessable_entity() fuer ConfigError-422 nutzt). Bei der #130<-main-Merge-
            # Aufloesung vom abweichenden "VALIDATION_ERROR" vereinheitlicht, damit derselbe
            # 422-Fall app-weit denselben Code liefert (DTB-63/DTB-34).
            content=Error(code="UNPROCESSABLE_ENTITY", message=message).model_dump(),
            # no-store wie auf ALLEN Fehlerpfaden (NF-01-Geist): auch ein Validierungsfehler
            # darf nicht von einem Proxy gecacht werden (#132<-main-Merge, ack-Test deckte die
            # bislang fehlende Header-Setzung auf).
            headers=NO_STORE_HEADERS,
        )
    return JSONResponse(
        status_code=400,
        content=Error(code="BAD_REQUEST", message=message).model_dump(),
        headers=NO_STORE_HEADERS,
    )


@app.get(
    "/v1/health",
    tags=["Health"],
    response_model=Health,
    dependencies=[Depends(get_runtime)],
    responses={
        503: {
            "model": Error,
            "description": (
                "G2 (noch) nicht lieferfaehig (Startup vor dem DI-Graph / interner "
                "Ausfall). Contract-Fehlerformat Error {code, message}, nie {detail}."
            ),
        }
    },
)
def health(response: Response) -> Health:
    """Liveness-Check (P0.3, Contract v1): bestaetigt, dass G2 erreichbar ist.

    ``200`` ``Health{status:"ok"}`` sobald der Runtime-/DI-Graph (lifespan) steht;
    ``503`` ``Error`` solange er fehlt: die ``get_runtime``-Dependency wirft dann
    ``RuntimeNotReadyError``, der registrierte Exception-Handler bildet sie
    contract-konform auf ``503`` ab (nie rohes ``500``/``{detail}``). ``get_runtime``
    dient hier nur als Ready-Gate (Wert ungenutzt) -> als Route-Dependency
    statt Endpoint-Parameter.

    Cache-Control: no-store auch auf dem 200-Pfad: ein gecachter Momentan-Zustand
    waere ein veraltetes Sicherheitssignal (NF-01).
    """
    response.headers.update(NO_STORE_HEADERS)
    return Health(status="ok")


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
        readings = runtime.reading_repo.get_latest(DEFAULT_SENSOR_ID, limit=1)
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
