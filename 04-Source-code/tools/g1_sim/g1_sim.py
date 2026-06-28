"""G1-Sensor-Simulator (Test-Tool, NICHT Teil des Produktiv-Builds).

Bedient den von G2 konsumierten G1-Contract (docs/api/v1/g1-consumed.openapi.yaml):
  GET /health   -> 200 {"status": "ok"}   oder 503 (state.health_down = true)
  GET /current  -> Snapshot (Pflicht-Trias + gemeinsamer measured_at + status)

Das Szenario wird bei JEDEM Request frisch aus der State-Datei gelesen -> die Sensorlage
laesst sich live umschalten (gruen/rot/stale/fault/down), ohne den Sim neu zu starten.

Start (aus 04-Source-code/):
    python tools/g1_sim/g1_sim.py --port 9101 --state tools/g1_sim/g1_state.json
G2 dagegen zeigen lassen:
    G1_BASE_URL=http://127.0.0.1:9101 G2_ENABLE_SCHEDULER=true uvicorn src.main:app
Szenario umschalten: State-JSON bearbeiten (siehe g1_state.example.json / README.md).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta

import uvicorn
from fastapi import FastAPI, Response

# Gruen-Default, falls keine State-Datei existiert -> der Sim laeuft sofort ohne Konfiguration.
_DEFAULT_STATE: dict = {
    "sensor_id": "anr-rwy-01",
    "surface_temp_c": 15.0,
    "air_temp_c": 16.0,
    "humidity_pct": 40.0,
    "pressure_hpa": 1013.0,
    "status": "ok",
    "age_s": 0,
    "health_down": False,
}

app = FastAPI(title="G1-Sensor-Simulator (Test)")


def _state_path() -> str:
    """Pfad der State-Datei: Env G1_SIM_STATE (von --state gesetzt), sonst neben diesem Skript."""
    return os.environ.get("G1_SIM_STATE") or os.path.join(
        os.path.dirname(__file__), "g1_state.json"
    )


def _load_state() -> dict:
    """Liest die State-Datei bei jedem Request (Live-Umschaltung); sonst Gruen-Default."""
    try:
        with open(_state_path(), encoding="utf-8") as fh:
            return {**_DEFAULT_STATE, **json.load(fh)}
    except FileNotFoundError:
        return dict(_DEFAULT_STATE)


@app.get("/health")
def health() -> Response:
    """G1-Verfuegbarkeit: 200 ok, oder 503 wenn state.health_down (G1-Ausfall simulieren)."""
    if _load_state().get("health_down"):
        return Response(status_code=503)
    return Response(content='{"status":"ok"}', media_type="application/json")


@app.get("/current")
def current() -> dict:
    """Aktueller Snapshot. age_s > 0 datiert measured_at zurueck (Stale-Test)."""
    state = _load_state()
    measured = datetime.now(UTC) - timedelta(seconds=float(state.get("age_s", 0)))
    return {
        "sensor_id": state["sensor_id"],
        "measured_at": measured.isoformat().replace("+00:00", "Z"),
        "surface_temp_c": state["surface_temp_c"],
        "air_temp_c": state["air_temp_c"],
        "humidity_pct": state["humidity_pct"],
        "pressure_hpa": state.get("pressure_hpa"),
        "status": state["status"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="G1-Sensor-Simulator (Test-Tool)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9101)
    parser.add_argument("--state", default=None, help="Pfad zur State-JSON (Live-Szenario)")
    args = parser.parse_args()
    if args.state:
        os.environ["G1_SIM_STATE"] = args.state
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
