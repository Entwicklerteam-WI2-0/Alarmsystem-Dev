"""FastAPI-Einstiegspunkt des G2-Backends (Vereisungserkennung ANR).

Grundgerüst (P0.3): startet den Server und stellt den Health-Check bereit.
Fachliche Endpoints (Ingest, Assessment, Serving) folgen in P1/P2 —
s. Backend-Konzept.md §7/§8 und Tasks+Projektplan.md.
"""

from fastapi import FastAPI

from src.api.v1 import router as v1_router

app = FastAPI(
    title="Alarmsystem-Backend G2 — Vereisungserkennung ANR",
    version="0.1.0",
)

# Versionierte /v1-Endpoints (Serving zu G3), z. B. GET /v1/thresholds (DTB-62).
app.include_router(v1_router)


@app.get("/v1/health")
def health() -> dict[str, str]:
    """Liveness-Check (P0.3): bestätigt, dass der Server erreichbar ist."""
    return {"status": "ok"}
