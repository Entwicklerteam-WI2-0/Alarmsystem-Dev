"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03). Aktuell: `GET /v1/thresholds`
(DTB-62) und `GET /v1/readings` (DTB-34).
Alle Endpoints hier sind **rein lesend** (RB-01-neutral).
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from src.api.responses import NO_STORE_HEADERS, service_unavailable
from src.api.runtime import Runtime, get_runtime
from src.config.constants import DEFAULT_SENSOR_ID
from src.config.loader import Thresholds
from src.model.schemas import Error, ReadingResponse
from src.storage.repository import RepositoryError

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


@router.get(
    "/readings",
    response_model=list[ReadingResponse],
    summary="Historie der Messwerte lesen",
    tags=["Readings"],
    responses={
        400: {
            "model": Error,
            "description": "Ungueltige Query-Parameter (z. B. from nach to).",
        },
        503: {
            "model": Error,
            "description": "G2 (noch) nicht lieferfaehig (Runtime nicht bereit / DB-Ausfall).",
        },
    },
)
def read_readings(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    response: Response,
    from_dt: Annotated[
        datetime | None,
        Query(
            alias="from",
            description="Untere Zeitgrenze (ISO-8601, UTC), inklusiv.",
        ),
    ] = None,
    to_dt: Annotated[
        datetime | None,
        Query(
            alias="to",
            description="Obere Zeitgrenze (ISO-8601, UTC), inklusiv.",
        ),
    ] = None,
    sensor_id: Annotated[
        str,
        Query(
            description="Sensor-ID; Default: einziger aktiver Sensor.",
            min_length=1,
            max_length=64,
        ),
    ] = DEFAULT_SENSOR_ID,
    limit: Annotated[
        int,
        Query(description="Maximale Anzahl Eintraege.", ge=1, le=1000),
    ] = 100,
    offset: Annotated[
        int,
        Query(description="Anzahl zu ueberspringender Zeilen.", ge=0),
    ] = 0,
    order: Annotated[
        Literal["asc", "desc"],
        Query(description="Sortierung nach measured_at."),
    ] = "desc",
) -> list[ReadingResponse]:
    """Liefert die Messwert-Historie fuer G3 (DTB-34, FA-03).

    Rein lesend (RB-01-neutral). Zeitstempel muessen zeitzonenbewusst sein;
    `from` darf nicht nach `to` liegen. Bei Persistenzfehlern wird fail-safe
    503 im Contract-Format `Error {code, message}` gemeldet.
    """
    response.headers.update(NO_STORE_HEADERS)

    try:
        readings = runtime.reading_repo.get_between(
            sensor_id=sensor_id,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=limit,
            offset=offset,
            order=order,
        )
    except ValueError as exc:
        # Ungueltige Parameter (from nach to, naive Zeitstempel) -> 400.
        return JSONResponse(  # type: ignore[return-value]
            status_code=400,
            content=Error(code="BAD_REQUEST", message=str(exc)).model_dump(),
        )
    except RepositoryError:
        # DB-Ausfall -> 503 (Fail-safe, NF-01-Geist).
        return service_unavailable("G2 momentan nicht lieferfaehig.")

    return [ReadingResponse(**reading.model_dump()) for reading in readings]
