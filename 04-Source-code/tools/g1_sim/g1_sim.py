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
import sys
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

# Contract-Statuswerte (g1-consumed.openapi.yaml). Abweichungen werden gewarnt, nicht erzwungen.
_VALID_STATUS = frozenset({"ok", "fault"})

app = FastAPI(title="G1-Sensor-Simulator (Test)")


def _warn(message: str) -> None:
    """Dev-Hinweis auf stderr (kein harter Fehler) -- z. B. Tippfehler in der State-Datei."""
    print(f"[g1_sim] WARN: {message}", file=sys.stderr)


def _state_path() -> str:
    """Pfad der State-Datei: Env G1_SIM_STATE (von --state gesetzt), sonst neben diesem Skript."""
    return os.environ.get("G1_SIM_STATE") or os.path.join(
        os.path.dirname(__file__), "g1_state.json"
    )


def _load_state() -> dict:
    """Liest die State-Datei bei jedem Request (Live-Umschaltung); sonst Gruen-Default.

    Robust gegen Hand-Editierfehler: invalides/fehlendes JSON -> Gruen-Default; unbekannte
    Keys (Tippfehler wie 'health_dow') und ein status ausserhalb [ok, fault] werden auf stderr
    gewarnt (kein harter Fehler), damit der Dev nicht im G2-Stack nach der Ursache sucht.
    """
    try:
        with open(_state_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        # Beim Live-Editieren ist die State-Datei kurzzeitig invalides JSON -> nicht mit
        # HTTP 500 crashen, sondern auf den Gruen-Default zurueckfallen (Dev-Komfort).
        return dict(_DEFAULT_STATE)
    if not isinstance(raw, dict):
        _warn(f"State-JSON ist kein Objekt ({type(raw).__name__}) -> Gruen-Default")
        return dict(_DEFAULT_STATE)
    unknown = set(raw) - set(_DEFAULT_STATE)
    if unknown:
        _warn(f"unbekannte State-Keys (Tippfehler?): {sorted(unknown)}")
    status = raw.get("status")
    if status is not None and status not in _VALID_STATUS:
        _warn(f"status={status!r} ausserhalb des Contracts {sorted(_VALID_STATUS)}")
    return {**_DEFAULT_STATE, **raw}


@app.get("/health")
def health() -> Response:
    """G1-Verfuegbarkeit: 200 ok, oder 503 wenn state.health_down (G1-Ausfall simulieren)."""
    if _load_state().get("health_down"):
        return Response(status_code=503)
    return Response(content='{"status":"ok"}', media_type="application/json")


@app.get("/current")
def current() -> dict:
    """Aktueller Snapshot. age_s >= 0 datiert measured_at zurueck (Stale-Test)."""
    state = _load_state()
    # Robust gegen Hand-Editierfehler: negatives age_s (measured_at in der Zukunft, ausserhalb
    # Spec) auf 0 klemmen; nicht-numerisches age_s ('foo') faengt der except (sonst 500 auf /current).
    try:
        age_s = max(0.0, float(state.get("age_s", 0)))
    except (TypeError, ValueError):
        _warn(f"age_s={state.get('age_s')!r} ist keine Zahl -> 0")
        age_s = 0.0
    measured = datetime.now(UTC) - timedelta(seconds=age_s)
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
