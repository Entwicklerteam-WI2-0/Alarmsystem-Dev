"""API-Key-Schutz fuer schreibende /v1-Endpoints (DTB-63, NF-07).

NF-07 verlangt fuer die Schwellwert-Konfiguration (und kuenftigen Fernzugriff)
Authentifizierung. Dieser Guard ist eine FastAPI-Dependency: er liest den
erwarteten Schluessel ausschliesslich aus der Umgebung (`G2_API_KEY`, nie im Code,
NF-07) und vergleicht ihn in konstanter Zeit mit dem `Authorization: Bearer
<key>`-Header.

Fail-safe-closed (NF-01-Geist): ist `G2_API_KEY` nicht gesetzt, wird JEDER
Schreibzugriff abgelehnt (503) statt unbewacht durchgelassen. Ein fehlender oder
falscher Schluessel ist 401. Beide Faelle bildet der Exception-Handler in main.py
contract-konform auf `Error {code, message}` ab (nie rohes 500/`{detail}`).

Bewusst Bearer-Schema (Standard, RFC 6750), nicht ein Custom-Header: zukunftssicher
fuer die spaetere ack-Auth (M3, Anfrage-G3) und sauber in den OpenAPI-Auto-Docs.
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.exceptions import ApiKeyNotConfiguredError, AuthenticationError

logger = logging.getLogger(__name__)

# Name der Umgebungsvariable mit dem erwarteten API-Key (NF-07: Secret nur aus Env).
API_KEY_ENV = "G2_API_KEY"

# auto_error=False: kein/ungueltiger Header soll NICHT FastAPIs Default-403/{detail}
# ausloesen, sondern unseren contract-konformen 401-Pfad. scheme_name/description
# erscheinen in den OpenAPI-Auto-Docs (/docs).
_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerApiKey",
    description="API-Key als 'Authorization: Bearer <key>' (NF-07, DTB-63).",
)


def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> None:
    """Dependency-Guard fuer schreibende Endpoints: erzwingt einen gueltigen API-Key.

    Raises:
        ApiKeyNotConfiguredError: `G2_API_KEY` ist nicht gesetzt -> 503 (fail-safe
            closed: lieber kein Schreibzugriff als ein unbewachter).
        AuthenticationError: Kein/ungueltiger Bearer-Token -> 401.
    """
    expected = os.environ.get(API_KEY_ENV)
    if not expected:
        # Leer/ungesetzt: Schreibzugriff ist nicht konfiguriert -> generell ablehnen.
        logger.warning("Schreibzugriff abgelehnt: %s nicht konfiguriert", API_KEY_ENV)
        raise ApiKeyNotConfiguredError("Schreibzugriff nicht konfiguriert.")
    provided = credentials.credentials if credentials is not None else None
    if provided is None or not _tokens_equal(provided, expected):
        logger.warning("Schreibzugriff abgelehnt: ungueltiger oder fehlender API-Key")
        raise AuthenticationError("Ungueltiger oder fehlender API-Key.")


def _tokens_equal(provided: str, expected: str) -> bool:
    """Konstant-Zeit-Vergleich zweier Token (gegen Timing-Angriffe).

    Bewusst ueber UTF-8-Bytes: `secrets.compare_digest` wirft bei einem `str` mit
    Nicht-ASCII-Zeichen einen `TypeError`. Da `provided` aus einem angreifer-
    kontrollierten Header stammt, wuerde ein Nicht-ASCII-Zeichen sonst einen
    unauthentifiziert ausloesbaren 500 erzeugen (Contract-Bruch, Robustheits-/
    DoS-Vektor). Bytes sind immer vergleichbar.
    """
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
