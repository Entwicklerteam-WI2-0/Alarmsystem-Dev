"""FastAPI-Einstiegspunkt des G2-Backends (Vereisungserkennung ANR).

Grundgerüst (P0.3): startet den Server und stellt den Health-Check bereit.
Fachliche Endpoints (Ingest, Assessment, Serving) folgen in P1/P2 —
s. Backend-Konzept.md §7/§8 und Tasks+Projektplan.md.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Alarmsystem-Backend G2 — Vereisungserkennung ANR",
    version="0.1.0",
)


@app.get("/v1/health")
def health() -> dict[str, str]:
    """Liveness-Check (P0.3): bestätigt, dass der Server erreichbar ist."""
    return {"status": "ok"}
