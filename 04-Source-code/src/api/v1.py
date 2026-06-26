"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03). Aktuell: `GET /v1/thresholds`
(DTB-62) — liefert die aktuell konfigurierten Schwellenwerte fuer das G3-Menue.
Alle Endpoints hier sind **rein lesend** (RB-01-neutral): kein Aktor, keine
Runway-Steuerung.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from src.api.responses import NO_STORE_HEADERS
from src.api.runtime import Runtime, get_runtime
from src.config.loader import Thresholds
from src.model.schemas import Error

router = APIRouter(prefix="/v1", tags=["v1"])


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
