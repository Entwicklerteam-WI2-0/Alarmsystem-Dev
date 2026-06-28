"""Geteilte, Contract-konforme HTTP-Antworten der /v1/-Naht (G2 -> G3).

Eine Quelle der Wahrheit fuer die 503-Antwort im Fehlerformat `Error {code, message}`
(E-36, Contract D) + `Cache-Control: no-store`. Beide Serving-Stellen — `assessment/
current` (main.py) und `thresholds` (api/v1.py) — antworten darueber identisch und
DRY: nie `{"detail": ...}` (FastAPI-Default, bricht die eingefrorene Naht), nie ein
von einem Proxy gecachter, ueberholter Ausfall (NF-01-Geist).
"""

from types import MappingProxyType

from fastapi.responses import JSONResponse

from src.model.schemas import Error

# Contract-Fehlercode "G2 (noch) nicht lieferfaehig" (503), s. openapi.yaml Error-Beispiel.
SERVICE_UNAVAILABLE_CODE = "SERVICE_UNAVAILABLE"
# Contract-Fehlercodes fuer die schreibende Naht (DTB-63): 401 (Auth) / 422 (Body).
UNAUTHORIZED_CODE = "UNAUTHORIZED"
UNPROCESSABLE_ENTITY_CODE = "UNPROCESSABLE_ENTITY"

# RFC 6750 §3: ein 401 auf einem Bearer-geschuetzten Endpoint MUSS den Challenge-Header
# `WWW-Authenticate` tragen, sonst wissen konforme Bearer-/OAuth-Clients (und OpenAPI-
# Codegen) nicht, dass Bearer-Auth erwartet wird. `realm` = menschenlesbares Schutzgebiet
# (der Auth-geschuetzte Schreibweg, NF-07/DTB-63).
WWW_AUTHENTICATE_BEARER = 'Bearer realm="G2-Write-API"'

# Sicherheits-/Echtzeit-Naht: weder Proxy noch Browser duerfen einen ueberholten Ausfall
# (503) ODER einen Momentan-/Konfig-Zustand (200) cachen. Ein gecachtes 503 (G2 laengst
# wieder da), ein gecachtes "green" oder gecachte Alt-Schwellen waeren ein veraltetes
# Sicherheitssignal (NF-01). Relevant erst hinter einem kuenftigen Reverse-Proxy, aber
# billig + korrekt. MappingProxyType = echte, read-only Konstante: faengt eine
# versehentliche Mutation (z. B. NO_STORE_HEADERS["X-Foo"] = ...) zur Laufzeit ab.
NO_STORE_HEADERS = MappingProxyType({"Cache-Control": "no-store"})


def service_unavailable(message: str) -> JSONResponse:
    """503 im Contract-Fehlerformat `Error {code, message}` + `Cache-Control: no-store`.

    Bewusst NICHT `HTTPException(detail=...)`: das liefert `{"detail": ...}` und bricht
    damit die eingefrorene Naht (Contract verlangt `{code, message}`). Die Nachricht
    bleibt generisch (keine internen Details/Secrets, Contract D / RB-01).
    """
    return _contract_error(503, SERVICE_UNAVAILABLE_CODE, message)


def unauthorized(message: str) -> JSONResponse:
    """401 im Contract-Fehlerformat `Error {code, message}` + `Cache-Control: no-store`.

    Fuer den API-Key-Guard (DTB-63/NF-07): kein/ungueltiger Schluessel. Bewusst NICHT
    FastAPIs Security-Default (403/`{detail}`), der die eingefrorene Naht braeche.
    Generische Nachricht (keine internen Details, Contract D).

    Traegt zusaetzlich den `WWW-Authenticate: Bearer`-Challenge-Header (RFC 6750 §3),
    den ein 401 auf einem Bearer-geschuetzten Endpoint zwingend braucht.
    """
    return _contract_error(
        401,
        UNAUTHORIZED_CODE,
        message,
        extra_headers={"WWW-Authenticate": WWW_AUTHENTICATE_BEARER},
    )


def unprocessable_entity(message: str) -> JSONResponse:
    """422 im Contract-Fehlerformat `Error {code, message}` + `Cache-Control: no-store`.

    Fuer Body-/Schema-Validierungsfehler (Contract D: 422 = Body-Schema-Validierung)
    statt FastAPIs Default-`{detail}`-Liste, damit die Fehlernaht einheitlich bleibt.
    """
    return _contract_error(422, UNPROCESSABLE_ENTITY_CODE, message)


def _contract_error(
    status_code: int,
    code: str,
    message: str,
    extra_headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Baut eine Contract-konforme Fehlerantwort `Error {code, message}` + no-store.

    Eine Quelle der Wahrheit fuer alle Fehler-Responses der Naht: nie `{"detail": ...}`
    (FastAPI-Default, bricht den Contract), nie ein gecachter Fehler (NF-01-Geist).
    `extra_headers` ergaenzt endpoint-spezifische Header (z. B. der 401-Challenge
    `WWW-Authenticate`), ohne die Basis-Header zu verlieren.
    """
    # NO_STORE_HEADERS ist read-only (MappingProxyType) -> in ein frisches dict kopieren,
    # bevor zusaetzliche Header gemergt werden (kein In-place-Mutationsversuch).
    headers = dict(NO_STORE_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(
        status_code=status_code,
        content=Error(code=code, message=message).model_dump(),
        headers=headers,
    )
