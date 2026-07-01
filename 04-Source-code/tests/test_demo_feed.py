"""Netzfreie Tests des Demo-Feed-Kerns (tools/demo/feed_core.py).

Gesichert werden zwei Dinge:
  1. Preset -> Ampelstufe: jedes aktive Preset-Center erzeugt ueber die ECHTE
     Produktivkaskade (assess_ice_risk, #182 Frostpunkt-Referenz) die benannte
     Stufe -- auch an den Dither-Extremen. Das ist die Regression gegen die
     Preset-Bugs 'yellow' (1,5 C -> GRUEN) und 'orange' (0,5 C -> GELB) aus feed.ps1.
  2. Ramp/Dither-Mechanik: die Rampe verletzt das Jump-Limit nicht, der Dither
     ueberschreitet das flatline_epsilon (0,15) -> der Feed bleibt "lebendig".

Alle Schwellen kommen aus der echten Default-Config (load_thresholds) -- keine
Hardcodes (NF-05). Die Presets werden bewusst gegen den Produktiv-Code geprueft,
nicht gegen eine Kopie der Schwellen.
"""

import pytest

from src.assessment.core import assess_ice_risk
from src.assessment.utils import calculate_dew_point
from src.config.loader import load_thresholds
from src.model.enums import RiskLevel
from tools.demo.feed_core import (
    DITHER_AIR_FACTOR,
    DITHER_SURFACE_C,
    EXPECTED_LEVEL,
    MAX_STEP_TEMP_C,
    PRESETS,
    FeedState,
    next_state,
    step_toward,
)

_THR = load_thresholds()
_LEVEL = {
    "green": RiskLevel.GREEN,
    "yellow": RiskLevel.YELLOW,
    "orange": RiskLevel.ORANGE,
    "red": RiskLevel.RED,
}
_ACTIVE = ["green", "yellow", "orange", "red"]


def _classify(surface_temp_c: float, air_temp_c: float, humidity_pct: float) -> RiskLevel:
    """Echter Produktivpfad: Magnus-Taupunkt + Vereisungskaskade (ohne Prognose)."""
    dew = calculate_dew_point(air_temp_c, humidity_pct)
    return assess_ice_risk(surface_temp_c, dew, _THR)


# --- 1. Preset -> Ampelstufe (gegen assess_ice_risk) -------------------------


@pytest.mark.parametrize("name", _ACTIVE)
def test_preset_center_erzeugt_erwartete_stufe(name: str) -> None:
    p = PRESETS[name]
    level = _classify(p.surface_temp_c, p.air_temp_c, p.humidity_pct)
    assert level is _LEVEL[EXPECTED_LEVEL[name]], f"{name}-Center erzeugt {level}, nicht erwartet"


@pytest.mark.parametrize("name", _ACTIVE)
def test_preset_bleibt_stufe_unter_dither(name: str) -> None:
    """An beiden Dither-Extremen (+/- Amplitude auf surface, air folgt) bleibt die Stufe stabil."""
    p = PRESETS[name]
    for sign in (1, -1):
        surface = p.surface_temp_c + sign * DITHER_SURFACE_C
        air = p.air_temp_c + sign * DITHER_SURFACE_C * DITHER_AIR_FACTOR
        level = _classify(surface, air, p.humidity_pct)
        assert level is _LEVEL[EXPECTED_LEVEL[name]], (
            f"{name}: Dither {sign:+d} kippt Stufe auf {level}"
        )


def test_yellow_preset_regression_nicht_gruen() -> None:
    """Regression feed.ps1: yellow=1,5 C zeigte GRUEN (> gelb_auffang 1,0). Jetzt GELB."""
    p = PRESETS["yellow"]
    assert p.surface_temp_c <= _THR.vereisung.t_s_gelb_auffang_c
    assert p.surface_temp_c > _THR.vereisung.t_s_gefrierpunkt_c  # nicht faelschlich ORANGE
    assert _classify(p.surface_temp_c, p.air_temp_c, p.humidity_pct) is RiskLevel.YELLOW


def test_orange_preset_regression_nicht_gelb() -> None:
    """Regression feed.ps1: orange=0,5 C zeigte GELB (> Gefrierpunkt 0,0). Jetzt ORANGE."""
    p = PRESETS["orange"]
    assert p.surface_temp_c <= _THR.vereisung.t_s_gefrierpunkt_c
    assert _classify(p.surface_temp_c, p.air_temp_c, p.humidity_pct) is RiskLevel.ORANGE


# --- 2. Ramp-/Dither-Mechanik ------------------------------------------------


def test_step_toward_haelt_jump_limit_ein() -> None:
    assert step_toward(0.0, 10.0, MAX_STEP_TEMP_C) == MAX_STEP_TEMP_C
    assert step_toward(0.0, -10.0, MAX_STEP_TEMP_C) == -MAX_STEP_TEMP_C
    assert step_toward(0.0, 0.3, MAX_STEP_TEMP_C) == 0.3  # <= max_step -> Ziel direkt


def test_dither_ueberschreitet_flatline_epsilon() -> None:
    """Der Surface-Dither muss > flatline_epsilon (0,15) schwingen, sonst kippt der
    Flatline-Fail-safe (NF-01) den statischen Feed nach 15 min auf unknown."""
    eps = _THR.datenqualitaet.flatline_epsilon_c
    state = FeedState()  # startet bereits auf dem red-Center (-2.0)
    surfaces = [next_state(state, PRESETS["red"], tick)["surface_temp_c"] for tick in range(20)]
    assert max(surfaces) - min(surfaces) > eps


def test_stale_und_down_bleiben_statisch() -> None:
    """Fail-safe-Presets duerfen NICHT dithern -- der Sensor soll als eingefroren/aus gelten."""
    for name in ("stale", "fault", "down"):
        state = FeedState()
        snaps = [next_state(state, PRESETS[name], tick)["surface_temp_c"] for tick in range(10)]
        assert max(snaps) - min(snaps) == 0.0, f"{name} darf nicht schwingen"


def test_next_state_schema_deckt_g1_sim_default() -> None:
    """Der Feed-Snapshot traegt exakt die Felder, die g1_sim._DEFAULT_STATE kennt
    (unbekannte Keys wuerde der Sim auf stderr warnen)."""
    from tools.g1_sim.g1_sim import _DEFAULT_STATE

    snap = next_state(FeedState(), PRESETS["green"], 0)
    assert set(snap) == set(_DEFAULT_STATE)


# --- 3. CLI-Helfer (g1_feed.py) ----------------------------------------------


def test_winter_scenario_durchlaeuft_alle_stufen() -> None:
    """Der Winter-Tagesgang muss ueber einen Zyklus alle vier aktiven Stufen anfahren."""
    from tools.demo.g1_feed import WINTER_CYCLE, winter_scenario

    period = sum(dur for _, dur in WINTER_CYCLE)
    seen = {winter_scenario(t) for t in range(0, int(period), 5)}
    assert {"green", "yellow", "orange", "red"} <= seen


def test_winter_scenario_ist_periodisch() -> None:
    from tools.demo.g1_feed import WINTER_CYCLE, winter_scenario

    period = sum(dur for _, dur in WINTER_CYCLE)
    assert winter_scenario(1.0) == winter_scenario(1.0 + period)


def test_state_roundtrip_und_scenario(tmp_path) -> None:
    """write_state -> read_state ist verlustfrei; read_scenario faellt bei Muell zurueck."""
    from tools.demo.g1_feed import read_scenario, read_state, write_state

    state_file = tmp_path / "g1_state.json"
    snap = next_state(FeedState(), PRESETS["orange"], 3)
    write_state(state_file, snap)
    assert read_state(state_file) == snap

    scenario_file = tmp_path / "scenario.txt"
    scenario_file.write_text("orange", encoding="ascii")
    assert read_scenario(scenario_file) == "orange"
    scenario_file.write_text("quatsch", encoding="ascii")
    assert read_scenario(scenario_file) == "red"  # unbekannt -> Fallback
    assert read_scenario(tmp_path / "fehlt.txt") == "red"  # fehlend -> Fallback
