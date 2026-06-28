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

# Contract-Fehlercodes (s. openapi.yaml Error-Beispiele). Benannte Konstanten statt
# Inline-Strings -> keine Tippfehler-Drift zwischen Endpoint und Spec.
SERVICE_UNAVAILABLE_CODE = "SERVICE_UNAVAILABLE"  # 503: G2 (noch) nicht lieferfaehig
BAD_REQUEST_CODE = "BAD_REQUEST"  # 400: Request-/Pfad-/Geschaeftsregel-Fehler (z. B. id < 1)
NOT_FOUND_CODE = "NOT_FOUND"  # 404: Ressource existiert nicht
ALARM_ALREADY_ACKNOWLEDGED_CODE = "ALARM_ALREADY_ACKNOWLEDGED"  # 409: Double-Ack (NF-09)
VALIDATION_ERROR_CODE = "VALIDATION_ERROR"  # 422: Body-Schema-Validierung

# Sicherheits-/Echtzeit-Naht: weder Proxy noch Browser duerfen einen ueberholten Ausfall
# (503) ODER einen Momentan-/Konfig-Zustand (200) cachen. Ein gecachtes 503 (G2 laengst
# wieder da), ein gecachtes "green" oder gecachte Alt-Schwellen waeren ein veraltetes
# Sicherheitssignal (NF-01). Relevant erst hinter einem kuenftigen Reverse-Proxy, aber
# billig + korrekt. MappingProxyType = echte, read-only Konstante: faengt eine
# versehentliche Mutation (z. B. NO_STORE_HEADERS["X-Foo"] = ...) zur Laufzeit ab.
NO_STORE_HEADERS = MappingProxyType({"Cache-Control": "no-store"})


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Contract-konforme Fehlerantwort `Error {code, message}` + `Cache-Control: no-store`.

    Eine Quelle der Wahrheit fuer ALLE /v1-Fehler (400/404/409/422/503): nie FastAPIs
    `{"detail": ...}` (bricht die eingefrorene Naht, Contract D), nie ein von einem Proxy
    gecachter Fehlerzustand (NF-01-Geist). Die Nachricht bleibt generisch — keine internen
    Details/Secrets (Contract D / RB-01).
    """
    return JSONResponse(
        status_code=status_code,
        content=Error(code=code, message=message).model_dump(),
        headers=NO_STORE_HEADERS,
    )


def service_unavailable(message: str) -> JSONResponse:
    """503 `Error {code, message}` (Spezialfall von `error_response`, eigener Name fuer
    den haeufigsten Fall: G2 nicht lieferfaehig)."""
    return error_response(503, SERVICE_UNAVAILABLE_CODE, message)
