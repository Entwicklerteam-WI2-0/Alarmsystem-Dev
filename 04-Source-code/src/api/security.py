"""API-Key-Schutz fuer schreibende v1-Endpoints (DTB-63, NF-07).

Der "Tuersteher" `require_api_key` ist eine FastAPI-Dependency, die schreibende
Endpoints (z. B. POST /v1/alarms/{id}/ack, POST /v1/config) schuetzt. Lesende
Endpoints bleiben offen. RB-01 bleibt unberuehrt: das ist reiner Zugangsschutz,
kein Aktor.

Methode (Prototyp/M3): statischer API-Key im Header `X-API-Key`, Soll-Wert
ausschliesslich aus der Umgebungsvariable `G2_API_KEY` (kein Secret im Code).
Bewusst wechselbar gehalten (Basic/JWT spaeter) — Naht-Entscheidung beim Architekt.
"""

import logging
import os
import secrets

from fastapi import Depends
from fastapi.security import APIKeyHeader

from src.api.exceptions import APIKeyMissingError, AuthenticationError

# Name der Umgebungsvariable mit dem serverseitigen Soll-Schluessel.
API_KEY_ENV = "G2_API_KEY"

logger = logging.getLogger(__name__)

# APIKeyHeader integriert sich in die generierte OpenAPI (securityScheme) und
# liest den Header `X-API-Key`. auto_error=False -> wir formulieren die Fehler selbst.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: str | None = Depends(api_key_header)) -> str:
    """Laesst nur Requests mit gueltigem X-API-Key durch.

    - Kein serverseitiger Schluessel konfiguriert -> 503 (Schreibzugriff fail-safe
      blockiert; lieber zu als versehentlich offen).
    - Fehlender/falscher Schluessel -> 401.
    Vergleich zeitkonstant (`secrets.compare_digest`) gegen Timing-Angriffe.

    Returns:
        Der validierte API-Key ( fuer Audit-Logging, NF-09).
    """
    expected = os.environ.get(API_KEY_ENV)
    if not expected:
        logger.warning("Schreibzugriff abgelehnt: G2_API_KEY nicht konfiguriert")
        raise APIKeyMissingError("Schreibzugriff nicht konfiguriert")
    if provided is None or not secrets.compare_digest(provided, expected):
        logger.warning("Schreibzugriff abgelehnt: ungueltiger oder fehlender API-Key")
        raise AuthenticationError("Ungueltiger oder fehlender API-Key")
    return provided
