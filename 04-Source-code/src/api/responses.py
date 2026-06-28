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

# Contract-Fehlercode fuer ungueltige Anfragen (400), s. openapi.yaml /v1/readings + /v1/alarms.
BAD_REQUEST_CODE = "BAD_REQUEST"

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
    return JSONResponse(
        status_code=503,
        content=Error(code=SERVICE_UNAVAILABLE_CODE, message=message).model_dump(),
        headers=NO_STORE_HEADERS,
    )


def bad_request(message: str) -> JSONResponse:
    """400 im Contract-Fehlerformat `Error {code, message}` + `Cache-Control: no-store`.

    Fuer Geschaeftsregel-/Bereichsfehler an der /v1-Naht (z. B. `from` nach `to`,
    `limit` ausserhalb des erlaubten Bereichs, ungueltiges `order` bei /v1/readings).
    Bewusst NICHT FastAPIs Default-Validierung (`HTTPException`/`422 {detail}`): die
    bricht die eingefrorene Naht (Contract verlangt `{code, message}`, openapi.yaml
    dokumentiert fuer /v1/readings genau `400 Error`). Die Meldung bleibt generisch
    (keine internen Details, Contract D / RB-01).
    """
    return JSONResponse(
        status_code=400,
        content=Error(code=BAD_REQUEST_CODE, message=message).model_dump(),
        headers=NO_STORE_HEADERS,
    )
