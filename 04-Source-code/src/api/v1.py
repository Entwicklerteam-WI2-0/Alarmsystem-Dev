"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03). Aktuell: `GET /v1/thresholds`
(DTB-62) — liefert die aktuell konfigurierten Schwellenwerte fuer das G3-Menue.
Alle Endpoints hier sind **rein lesend** (RB-01-neutral): kein Aktor, keine
Runway-Steuerung.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.config.loader import ConfigError, Thresholds, load_thresholds

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["v1"])


def get_thresholds() -> Thresholds:
    """Laedt die aktuellen Schwellenwerte (DTB-15).

    Als eigene Dependency ausgelegt, damit Tests sie ueberschreiben koennen und der
    Endpoint die Werte nie hardcodiert. Bei Fehlkonfiguration wird fail-safe ein
    `503` gemeldet — ohne interne Pfade/Details zu leaken (NF-01-Geist).
    """
    try:
        return load_thresholds()
    except (ConfigError, OSError) as exc:
        logger.error("Schwellenwert-Config nicht ladbar: %s", exc)
        raise HTTPException(
            status_code=503, detail="Schwellenwert-Konfiguration nicht verfuegbar"
        ) from exc


@router.get("/thresholds", response_model=Thresholds, summary="Aktuelle Schwellenwerte lesen")
def read_thresholds(thresholds: Annotated[Thresholds, Depends(get_thresholds)]) -> Thresholds:
    """Liefert die aktuell konfigurierten Schwellenwerte (NF-05) fuer G3.

    Rein lesend (RB-01-neutral). Werte kommen ausschliesslich aus dem Loader (DTB-15);
    Aendern erfolgt spaeter ueber einen separaten, Auth-geschuetzten Endpoint (NF-07).
    """
    return thresholds
