"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03). Aktuell: `GET /v1/thresholds`
(DTB-62) — liefert die aktuell konfigurierten Schwellenwerte fuer das G3-Menue.
Alle Endpoints hier sind **rein lesend** (RB-01-neutral): kein Aktor, keine
Runway-Steuerung.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from src.api.responses import NO_STORE_HEADERS
from src.config.loader import ConfigError, Thresholds, load_thresholds
from src.model.schemas import Error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["v1"])


class ThresholdsUnavailableError(RuntimeError):
    """Schwellenwert-Config nicht ladbar -> fail-safe 503 (Contract `Error {code,message}`).

    Eigene Exception statt `HTTPException(detail=...)`: ein per `detail` formatierter 503
    wuerde `{"detail": ...}` liefern und damit die eingefrorene Naht brechen (Contract
    verlangt `{code, message}`). Der in `main.py` registrierte Exception-Handler bildet
    diese Exception contract-konform auf 503 ab — analog zu `RuntimeNotReadyError`. So
    bleibt `get_thresholds` eine ueberschreibbare Dependency (Testbarkeit) UND der
    Fehler-Contract gewahrt. Die Exception-Nachricht (ggf. mit internem Pfad) landet nur
    im Server-Log, nie im Response (kein Leak).
    """


def get_thresholds() -> Thresholds:
    """Laedt die aktuellen Schwellenwerte (DTB-15).

    Als eigene Dependency ausgelegt, damit Tests sie ueberschreiben koennen und der
    Endpoint die Werte nie hardcodiert. Bei Fehlkonfiguration wird fail-safe ein `503`
    gemeldet (ueber `ThresholdsUnavailableError` -> Handler in main.py) — ohne interne
    Pfade/Details zu leaken (NF-01-Geist).
    """
    try:
        return load_thresholds()
    except (ConfigError, OSError) as exc:
        logger.error("Schwellenwert-Config nicht ladbar: %s", exc)
        raise ThresholdsUnavailableError(str(exc)) from exc


@router.get(
    "/thresholds",
    response_model=Thresholds,
    summary="Aktuelle Schwellenwerte lesen",
    responses={
        503: {
            "model": Error,
            "description": "Schwellenwert-Konfiguration nicht verfuegbar (Fehlkonfiguration).",
        }
    },
)
def read_thresholds(
    thresholds: Annotated[Thresholds, Depends(get_thresholds)],
    response: Response,
) -> Thresholds:
    """Liefert die aktuell konfigurierten Schwellenwerte (NF-05) fuer G3.

    Rein lesend (RB-01-neutral). Werte kommen ausschliesslich aus dem Loader (DTB-15);
    Aendern erfolgt spaeter ueber einen separaten, Auth-geschuetzten Endpoint (NF-07).

    `Cache-Control: no-store`: Schwellen sind die Kalibrierung eines Fail-safe-Systems.
    Ein Proxy/Browser, der ueberholte Schwellen ausliefert, wuerde G3 einen falschen
    Betriebspunkt anzeigen (NF-01-Geist). Eine Quelle/Konvention mit `assessment/current`
    (kurzlebiger `max-age` waere ebenfalls vertretbar, da Schwellen sich selten aendern).
    """
    response.headers.update(NO_STORE_HEADERS)
    return thresholds
