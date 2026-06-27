"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03). Lesend:
`GET /v1/thresholds` (DTB-62). Schreibend (API-Key-geschuetzt, NF-07):
`POST /v1/alarms/{id}/ack` (DTB-63) und `POST /v1/config` (DTB-63).
Alle Endpoints sind informations- oder konfigurationsbezogen (RB-01-neutral).
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.responses import JSONResponse

from src.api.responses import NO_STORE_HEADERS
from src.api.runtime import Runtime, get_runtime
from src.api.security import require_api_key
from src.app_factory import build_runtime
from src.config.loader import ConfigError, Thresholds, save_thresholds
from src.model.enums import AuditEventType
from src.model.schemas import Acknowledgement, AckRequest, AuditLogEntry, Error
from src.storage.acknowledgement_repository import (
    AlarmAlreadyAcknowledgedError,
    AlarmNotFoundError,
)
from src.storage.repository import RepositoryError

logger = logging.getLogger(__name__)

# Kein Router-weiter Tag: jeder Endpoint deklariert seinen Ressourcen-Tag selbst
# (wie assessment/current -> "Assessment" in main.py), damit die FastAPI-Auto-Docs
# (/docs, /openapi.json) dieselbe Gruppierung zeigen wie die eingefrorene openapi.yaml.
router = APIRouter(prefix="/v1")


def get_thresholds(runtime: Annotated[Runtime, Depends(get_runtime)]) -> Thresholds:
    """Aktive Schwellenwerte = die zur Laufzeit geladenen (`runtime.thresholds`).

    Bewusst KEIN Disk-Read pro Request: der Endpoint spiegelt exakt die Schwellen, die
    die Bewertungslogik gerade verwendet (eine Quelle der Wahrheit, Konsistenz mit
    assessment/current) — statt einer Datei, die von der laufenden Bewertung abweichen
    koennte. Geladen wird genau einmal beim Start (`build_runtime` -> `load_thresholds`);
    eine geaenderte Config greift nach einem kontrollierten Neustart/Reload (NF-07).
    Eigene Dependency, damit Tests sie via `app.dependency_overrides` ersetzen koennen
    und der Endpoint nie hardcodiert. Bei nicht bereitem Runtime (z. B. Config beim Start
    nicht ladbar) meldet `get_runtime` fail-safe `RuntimeNotReadyError` -> 503.
    """
    return runtime.thresholds


@router.get(
    "/thresholds",
    response_model=Thresholds,
    summary="Aktuelle Schwellenwerte lesen",
    tags=["Thresholds"],
    responses={
        503: {
            "model": Error,
            "description": "G2 (noch) nicht lieferfaehig (Runtime nicht bereit).",
        }
    },
)
def read_thresholds(
    thresholds: Annotated[Thresholds, Depends(get_thresholds)],
    response: Response,
) -> Thresholds:
    """Liefert die aktuell konfigurierten Schwellenwerte (NF-05) fuer G3.

    Rein lesend (RB-01-neutral). Werte kommen aus dem zur Laufzeit geladenen
    Runtime-Graph (DTB-15); Aendern erfolgt spaeter ueber einen separaten,
    Auth-geschuetzten Endpoint (NF-07).

    `Cache-Control: no-store`: Schwellen sind die Kalibrierung eines Fail-safe-Systems.
    Ein Proxy/Browser, der ueberholte Schwellen ausliefert, wuerde G3 einen falschen
    Betriebspunkt anzeigen (NF-01-Geist). Eine Konvention mit `assessment/current`.
    """
    response.headers.update(NO_STORE_HEADERS)
    return thresholds


@router.post(
    "/alarms/{id}/ack",
    dependencies=[Depends(require_api_key)],
    response_model=Acknowledgement,
    summary="Alarm quittieren",
    tags=["Alarms"],
    responses={
        401: {"model": Error, "description": "Fehlender oder ungueltiger API-Key."},
        404: {"model": Error, "description": "Alarm mit dieser ID existiert nicht."},
        409: {
            "model": Error,
            "description": "Alarm ist bereits quittiert/geschlossen.",
        },
        503: {"model": Error, "description": "G2 momentan nicht lieferfaehig."},
    },
)
def acknowledge_alarm(
    id: Annotated[int, Path(ge=1)],
    request: AckRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
    response: Response,
) -> Acknowledgement | JSONResponse:
    """Quittiert einen Alarm. RB-01: rein dokumentierend, keine Rueckkopplung zur Anlage."""
    response.headers.update(NO_STORE_HEADERS)
    now = datetime.now(UTC)
    try:
        ack = runtime.ack_repo.acknowledge(id, request.operator, request.note, now)
    except AlarmNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=Error(code="NOT_FOUND", message=str(exc)).model_dump(),
            headers=NO_STORE_HEADERS,
        )
    except AlarmAlreadyAcknowledgedError as exc:
        return JSONResponse(
            status_code=409,
            content=Error(code="ALARM_ALREADY_ACKNOWLEDGED", message=str(exc)).model_dump(),
            headers=NO_STORE_HEADERS,
        )
    except RepositoryError as exc:
        logger.error("Quittierung fuer Alarm %s fehlgeschlagen: %s", id, exc)
        return JSONResponse(
            status_code=503,
            content=Error(
                code="SERVICE_UNAVAILABLE", message="G2 momentan nicht lieferfaehig."
            ).model_dump(),
            headers=NO_STORE_HEADERS,
        )
    except Exception:  # noqa: BLE001 - Serving darf nie als 500 brechen
        logger.exception("Unerwarteter Fehler bei Quittierung von Alarm %s", id)
        return JSONResponse(
            status_code=503,
            content=Error(
                code="SERVICE_UNAVAILABLE", message="G2 momentan nicht lieferfaehig."
            ).model_dump(),
            headers=NO_STORE_HEADERS,
        )

    # Audit-Trail (NF-09). Ein Audit-Fehl nach erfolgreicher Quittierung wird geloggt,
    # aendert aber den bereits persistierten Zustand nicht.
    try:
        runtime.audit_repo.append(_build_ack_audit_entry(id, request.operator, request.note, now))
    except Exception as exc:  # noqa: BLE001
        logger.error("Audit-Eintrag fuer Alarm-Quittierung %s fehlgeschlagen: %s", id, exc)

    return ack


def _build_ack_audit_entry(
    alarm_id: int, operator: str, note: str | None, ts: datetime
) -> AuditLogEntry:
    """Baut den Audit-Log-Eintrag fuer eine Quittierung."""
    return AuditLogEntry(
        ts=ts,
        event_type=AuditEventType.ALARM_ACKNOWLEDGED,
        entity_type="alarm",
        entity_id=alarm_id,
        actor=operator,
        detail={"note": note},
    )


@router.post(
    "/config",
    dependencies=[Depends(require_api_key)],
    response_model=Thresholds,
    summary="Schwellenwerte aktualisieren",
    tags=["Thresholds"],
    responses={
        401: {"model": Error, "description": "Fehlender oder ungueltiger API-Key."},
        422: {"model": Error, "description": "Ungueltige Schwellenwerte."},
        503: {"model": Error, "description": "G2 momentan nicht lieferfaehig."},
    },
)
def update_config(
    thresholds: Thresholds,
    request: Request,
    runtime: Annotated[Runtime, Depends(get_runtime)],
    response: Response,
) -> Thresholds | JSONResponse:
    """Schreibt neue Schwellenwerte und laedt die Runtime neu (NF-05/NF-07).

    RB-01: reine Konfiguration, keine Rueckkopplung zur physischen Anlage.
    """
    response.headers.update(NO_STORE_HEADERS)

    try:
        save_thresholds(thresholds)
    except ConfigError as exc:
        return JSONResponse(
            status_code=422,
            content=Error(code="UNPROCESSABLE_ENTITY", message=str(exc)).model_dump(),
            headers=NO_STORE_HEADERS,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Schwellenwerte konnten nicht geschrieben werden")
        return JSONResponse(
            status_code=503,
            content=Error(
                code="SERVICE_UNAVAILABLE", message="G2 momentan nicht lieferfaehig."
            ).model_dump(),
            headers=NO_STORE_HEADERS,
        )

    try:
        # [DEVIATION] M3-Prototyp: Kein Locking fuer parallele POST /v1/config.
        # Zwei gleichzeitige Requests koennen sich bei app.state.runtime ueberschreiben;
        # fuer den Prototypen akzeptabel, weil Schreibzugriff API-Key-geschuetzt und
        # Bedienperson koordiniert. Echte Serialisierung noetig, falls automatisierte
        # Config-Updates parallel eingehen (s. ADR E-40 Schicht 4).
        request.app.state.runtime = build_runtime()
    except Exception as exc:  # noqa: BLE001
        logger.error("Runtime konnte nach Config-Update nicht neu geladen werden: %s", exc)
        return JSONResponse(
            status_code=503,
            content=Error(
                code="SERVICE_UNAVAILABLE",
                message="Config gespeichert, aber Runtime-Reload fehlgeschlagen.",
            ).model_dump(),
            headers=NO_STORE_HEADERS,
        )

    return request.app.state.runtime.thresholds
