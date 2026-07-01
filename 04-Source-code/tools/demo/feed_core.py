"""Reine, netzfreie Kern-Logik des Demo-Feeds (tools/demo/g1_feed.py).

Getrennt vom CLI/Loop, damit die Preset->Ampel-Zuordnung und die Ramp-/Dither-
Mechanik OHNE Netzwerk gegen die Produktivkaskade `assess_ice_risk` testbar sind
(test_demo_feed.py). Kein Import aus `src` hier -> der Kern bleibt eine reine,
seiteneffektfreie Bibliothek; die Verdrahtung gegen die echte Bewertungslogik
passiert nur im Test.

Portiert die Logik aus dem fruehen `Alarmsystem-Demo/feed.ps1` nach cross-platform
Python (Variante A): atomares `g1_state.json`, Dither > flatline_epsilon (0,15),
sanfte Rampen < Jump-Limit (5 C/min). Korrigiert dabei ZWEI Preset-Bugs, die unter
der aktuellen Config (t_s_gefrierpunkt=0,0 / t_s_gelb_auffang=1,0) die falsche
Ampelstufe erzeugten:
  * 'yellow' war 1,5 C  (> gelb_auffang 1,0)  -> zeigte GRUEN  -> jetzt 0,5 C
  * 'orange' war 0,5 C  (> Gefrierpunkt 0,0)  -> zeigte GELB   -> jetzt -0,5 C
Die neuen Center sind gegen die #182-Kaskade (Frostpunkt-Referenz unter 0 C)
verifiziert (test_demo_feed.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# --- Feld-Konstanten (Schema == g1_sim._DEFAULT_STATE) -----------------------
SENSOR_ID = "anr-rwy-01"
PRESSURE_HPA = 1013.0
DEFAULT_INTERVAL_S = 18  # 1 C / 18 s = 3,3 C/min < Jump-Limit 5 C/min

# --- Ramp-Schrittweiten pro Tick (Center-Annaeherung) ------------------------
MAX_STEP_TEMP_C = 1.0
MAX_STEP_HUMIDITY = 5.0
MAX_STEP_MOISTURE = 6.0
MAX_STEP_WIND = 1.0

# --- Dither-Amplituden (nur bei aktiven Presets) -----------------------------
# Der Surface-Dither MUSS > flatline_epsilon (0,15) schwingen, sonst kippt der
# Flatline-Fail-safe (NF-01) den statischen Feed nach 15 min auf unknown.
DITHER_SURFACE_C = 0.25
DITHER_AIR_FACTOR = 0.4
DITHER_WIND = 0.6
DITHER_MOISTURE = 0.4


@dataclass(frozen=True)
class Preset:
    """Zielwerte (Center) einer Szenario-Stufe + Fail-safe-Demoschalter."""

    surface_temp_c: float
    air_temp_c: float
    humidity_pct: float
    surface_moisture_pct: float
    wind_speed_ms: float
    status: str = "ok"
    down: bool = False
    age_s: float = 0.0

    @property
    def active(self) -> bool:
        """True nur bei frischem, gesundem, erreichbarem Sensor -> dann wird gedithert."""
        return self.status == "ok" and not self.down and self.age_s == 0


# Szenario-Presets. Die vier aktiven Stufen sind gegen assess_ice_risk (#182,
# Frostpunkt) verifiziert; stale/fault/down demonstrieren die Fail-safe-Pfade
# (NF-01) ueber age_s / status / health_down (der Sim datiert measured_at zurueck
# bzw. liefert 503).
PRESETS: dict[str, Preset] = {
    "green": Preset(5.0, 5.0, 50.0, 15.0, 3.0),
    "yellow": Preset(0.5, 1.5, 88.0, 70.0, 4.0),
    "orange": Preset(-0.5, -0.5, 95.0, 88.0, 5.0),
    "red": Preset(-2.0, -1.0, 98.0, 96.0, 6.0),
    "stale": Preset(-2.0, -1.0, 98.0, 96.0, 6.0, age_s=200.0),
    "fault": Preset(-2.0, -1.0, 98.0, 96.0, 6.0, status="fault"),
    "down": Preset(-2.0, -1.0, 98.0, 96.0, 6.0, down=True),
}

# Aktive Presets, deren Center die benannte Ampelstufe erzeugen MUSS (Regression
# gegen die Preset-Bugs). stale/fault/down landen ueber die Fail-safe-Pipeline auf
# unknown und werden daher NICHT gegen assess_ice_risk geprueft.
EXPECTED_LEVEL: dict[str, str] = {
    "green": "green",
    "yellow": "yellow",
    "orange": "orange",
    "red": "red",
}


@dataclass
class FeedState:
    """Veraenderliche Rampenbasis zwischen zwei Ticks (Center-Naeherung)."""

    surface_temp_c: float = -2.0
    air_temp_c: float = -1.0
    humidity_pct: float = 98.0
    surface_moisture_pct: float = 96.0
    wind_speed_ms: float = 6.0

    @classmethod
    def from_snapshot(cls, snap: dict | None) -> FeedState:
        """Startbasis aus einem vorhandenen g1_state.json (nahtloser Wiederanlauf)."""
        if not isinstance(snap, dict):
            return cls()
        base = cls()
        for field in (
            "surface_temp_c",
            "air_temp_c",
            "humidity_pct",
            "surface_moisture_pct",
            "wind_speed_ms",
        ):
            value = snap.get(field)
            if isinstance(value, int | float):
                setattr(base, field, float(value))
        return base


def step_toward(current: float, target: float, max_step: float) -> float:
    """Naehert `current` um hoechstens `max_step` an `target` an (Sprung-Guard-sicher)."""
    delta = target - current
    if abs(delta) <= max_step:
        return target
    return current + max_step if delta > 0 else current - max_step


def next_state(state: FeedState, preset: Preset, tick: int) -> dict:
    """Rampt den Feed einen Tick Richtung Preset, dithert aktive Szenarien und
    liefert das serialisierbare g1_state.json-Objekt (Schema == g1_sim._DEFAULT_STATE).

    Mutiert `state` (die Rampenbasis) und gibt den Snapshot zurueck.
    """
    state.surface_temp_c = step_toward(state.surface_temp_c, preset.surface_temp_c, MAX_STEP_TEMP_C)
    state.air_temp_c = step_toward(state.air_temp_c, preset.air_temp_c, MAX_STEP_TEMP_C)
    state.humidity_pct = step_toward(state.humidity_pct, preset.humidity_pct, MAX_STEP_HUMIDITY)
    state.surface_moisture_pct = step_toward(
        state.surface_moisture_pct, preset.surface_moisture_pct, MAX_STEP_MOISTURE
    )
    state.wind_speed_ms = step_toward(state.wind_speed_ms, preset.wind_speed_ms, MAX_STEP_WIND)

    # Lebendiges Dither nur bei aktiven (ok, frisch, erreichbar) Szenarien; stale/
    # fault/down bleiben statisch (der Fail-safe-Pfad soll sie gerade NICHT retten).
    osc = DITHER_SURFACE_C * math.sin(tick * 0.7) if preset.active else 0.0
    wind_jit = DITHER_WIND * math.sin(tick * 1.3) if preset.active else 0.0
    sm_jit = DITHER_MOISTURE * math.sin(tick * 0.5) if preset.active else 0.0

    surface = round(state.surface_temp_c + osc, 4)
    air = round(state.air_temp_c + osc * DITHER_AIR_FACTOR, 4)
    wind = round(max(0.0, state.wind_speed_ms + wind_jit), 1)
    moist = round(min(100.0, max(0.0, state.surface_moisture_pct + sm_jit)), 1)

    return {
        "sensor_id": SENSOR_ID,
        "surface_temp_c": surface,
        "air_temp_c": air,
        "humidity_pct": round(state.humidity_pct, 2),
        "pressure_hpa": PRESSURE_HPA,
        "surface_moisture_pct": moist,
        "wind_speed_ms": wind,
        "status": preset.status,
        "age_s": preset.age_s,
        "health_down": preset.down,
    }
