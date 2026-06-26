"""Geteilte, Contract-konforme HTTP-Antworten der /v1/-Naht (G2 -> G3).

Eine Quelle der Wahrheit fuer die 503-Antwort im Fehlerformat `Error {code, message}`
(E-36, Contract D) + `Cache-Control: no-store`. Beide Serving-Stellen — `assessment/
current` (main.py) und `thresholds` (api/v1.py) — antworten darueber identisch und
DRY: nie `{"detail": ...}` (FastAPI-Default, bricht die eingefrorene Naht), nie ein
von einem Proxy gecachter, ueberholter Ausfall (NF-01-Geist).
"""

from fastapi.responses import JSONResponse

from src.model.schemas import Error

# Contract-Fehlercode "G2 (noch) nicht lieferfaehig" (503), s. openapi.yaml Error-Beispiel.
SERVICE_UNAVAILABLE_CODE = "SERVICE_UNAVAILABLE"

# Sicherheits-/Echtzeit-Naht: weder Proxy noch Browser duerfen einen ueberholten Ausfall
# (503) ODER einen Momentan-/Konfig-Zustand (200) cachen. Ein gecachtes 503 (G2 laengst
# wieder da), ein gecachtes "green" oder gecachte Alt-Schwellen waeren ein veraltetes
# Sicherheitssignal (NF-01). Relevant erst hinter einem kuenftigen Reverse-Proxy, aber
# billig + korrekt.
NO_STORE_HEADERS = {"Cache-Control": "no-store"}


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
