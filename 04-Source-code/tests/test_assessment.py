"""Tests für das Bewertungsmodul (DTB-38).

Ziel: ≥ 80 % Coverage der Bewertungslogik, inkl. beider dokumentierter Vorfälle
und des Fail-safe-Verhaltens bei fehlendem/unbestimmbarem Taupunkt (NF-01).

Alle Schwellen kommen aus der Default-Config (DTB-15); es werden keine
Hardcodes verwendet.
"""

import pytest

from src.assessment import assess_ice_risk
from src.config.loader import load_thresholds
from src.model.enums import RiskLevel


@pytest.fixture(scope="module")
def thresholds():
    """Geladene Default-Schwellen (Schwellenwerte.md §2)."""
    return load_thresholds()


# ---------------------------------------------------------------------------
# Kaskade: ROT > ORANGE > GELB > GRÜN
# ---------------------------------------------------------------------------


def test_rot_wenn_gefroren_und_kondensation(thresholds):
    # T_s am Gefrierpunkt, T_d höher -> ΔT = 0 -> Kondensation
    assert assess_ice_risk(0.0, 0.0, thresholds) == RiskLevel.RED


def test_rot_wenn_oberflaeche_unter_taupunkt(thresholds):
    assert assess_ice_risk(-2.0, -1.0, thresholds) == RiskLevel.RED


def test_orange_wenn_gefroren_und_feucht(thresholds):
    # ΔT = 0.5 -> feucht, aber noch nicht Kondensation -> ORANGE
    assert assess_ice_risk(-1.0, -1.5, thresholds) == RiskLevel.ORANGE


def test_orange_wenn_gefroren_und_trocken_dann_nicht_orange(thresholds):
    # ΔT = 2.0 -> nicht feucht -> nicht ORANGE; T_s <= 1.0 -> GELB
    assert assess_ice_risk(-1.0, -3.0, thresholds) == RiskLevel.YELLOW


def test_gelb_wenn_kalt_aber_nicht_gefroren(thresholds):
    # T_s im Auffangbereich 0..+1.0, egal ob feucht oder trocken
    assert assess_ice_risk(0.5, -5.0, thresholds) == RiskLevel.YELLOW


def test_gelb_durch_prognose(thresholds):
    # Aktuell GRÜN, aber Prognose sagt Gefrieren in ≤ 30 min
    assert assess_ice_risk(2.0, -5.0, thresholds, forecast_surface_temp_c=-1.0) == RiskLevel.YELLOW


def test_gruen_wenn_warm_und_keine_prognose(thresholds):
    assert assess_ice_risk(2.0, 0.0, thresholds) == RiskLevel.GREEN


# ---------------------------------------------------------------------------
# Dokumentierte Vorfälle
# ---------------------------------------------------------------------------


def test_vorfall_1_kein_fehlalarm_bei_trockener_kalter_oberflaeche(thresholds):
    """Vorfall 1: Luft -2,1 °C, hohe Luftfeuchte, aber trockene Oberfläche.

    Übersetzt: T_s kalt, aber T_d weit darunter -> ΔT > 1.0.
    Frühere RH≥90 %-Logik hätte fälschlich ORANGE erzeugt (E-33 entfernt).
    """
    t_s = -2.1
    t_d = -10.0  # trockene Oberfläche -> ΔT = 7.9
    assert assess_ice_risk(t_s, t_d, thresholds) == RiskLevel.YELLOW


def test_vorfall_2_vereisung_erkannt_bei_kalter_oberflaeche(thresholds):
    """Vorfall 2: Luft +1,2 °C, aber Oberfläche < 0 °C und feucht -> Eis."""
    t_s = -1.0
    t_d = -1.2  # ΔT = 0.2 -> feucht, nahe Kondensation
    result = assess_ice_risk(t_s, t_d, thresholds)
    assert result in (RiskLevel.ORANGE, RiskLevel.RED)


# ---------------------------------------------------------------------------
# Fail-safe (NF-01)
# ---------------------------------------------------------------------------


def test_fehlender_taupunkt_bei_gefrorener_oberflaeche_ist_orange(thresholds):
    """T_d unbestimmbar -> Feuchte=wahr (konservativ); T_s ≤ 0 -> ORANGE."""
    assert assess_ice_risk(-1.0, None, thresholds) == RiskLevel.ORANGE


def test_fehlender_taupunkt_bei_warmer_oberflaeche_ist_gelb(thresholds):
    """T_d unbestimmbar -> nie GRÜN; T_s > 0 -> GELB."""
    assert assess_ice_risk(2.0, None, thresholds) == RiskLevel.YELLOW


def test_fehlender_taupunkt_mit_prognose_bleibt_konservativ(thresholds):
    """Auch mit Prognose darf fehlendes T_d nicht zu GRÜN führen."""
    assert assess_ice_risk(2.0, None, thresholds, forecast_surface_temp_c=5.0) == RiskLevel.YELLOW


# ---------------------------------------------------------------------------
# Grenzwerte
# ---------------------------------------------------------------------------


def test_grenzwert_t_s_genau_0_mit_delta_t_0_ist_rot(thresholds):
    assert assess_ice_risk(0.0, 0.0, thresholds) == RiskLevel.RED


def test_grenzwert_t_s_genau_0_mit_delta_t_1_ist_orange(thresholds):
    # ΔT = 1.0 -> genau Feuchte-Schwelle, aber nicht Kondensation
    assert assess_ice_risk(0.0, -1.0, thresholds) == RiskLevel.ORANGE


def test_grenzwert_t_s_genau_1_ohne_feuchte_ist_gelb(thresholds):
    # T_s = +1.0 -> genau GELB-Auffang, T_d weit weg -> nicht feucht
    assert assess_ice_risk(1.0, -10.0, thresholds) == RiskLevel.YELLOW


def test_grenzwert_t_s_knapp_ueber_1_ist_gruen(thresholds):
    assert assess_ice_risk(1.01, -10.0, thresholds) == RiskLevel.GREEN


# ---------------------------------------------------------------------------
# Ungültige Zahlen (NF-01)
# ---------------------------------------------------------------------------


def test_nan_oberflaechentemperatur_ist_unknown(thresholds):
    assert assess_ice_risk(float("nan"), 0.0, thresholds) == RiskLevel.UNKNOWN


def test_inf_oberflaechentemperatur_ist_unknown(thresholds):
    assert assess_ice_risk(float("inf"), 0.0, thresholds) == RiskLevel.UNKNOWN


def test_nan_taupunkt_ist_unknown(thresholds):
    assert assess_ice_risk(0.0, float("nan"), thresholds) == RiskLevel.UNKNOWN


def test_inf_taupunkt_ist_unknown(thresholds):
    assert assess_ice_risk(0.0, float("inf"), thresholds) == RiskLevel.UNKNOWN


def test_ungueltige_prognose_wird_ignoriert(thresholds):
    """NaN/inf in der optionalen Prognose darf nicht GRÜN erzwingen."""
    assert (
        assess_ice_risk(2.0, 0.0, thresholds, forecast_surface_temp_c=float("nan"))
        == RiskLevel.GREEN
    )
    assert (
        assess_ice_risk(2.0, 0.0, thresholds, forecast_surface_temp_c=float("inf"))
        == RiskLevel.GREEN
    )
