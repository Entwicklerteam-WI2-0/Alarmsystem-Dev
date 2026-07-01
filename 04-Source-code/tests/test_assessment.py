"""Tests für das Bewertungsmodul (DTB-38).

Ziel: ≥ 80 % Coverage der Bewertungslogik, inkl. beider dokumentierter Vorfälle
und des Fail-safe-Verhaltens bei fehlendem/unbestimmbarem Taupunkt (NF-01).

Alle Schwellen kommen aus der Default-Config (DTB-15); es werden keine
Hardcodes verwendet.
"""

import pytest

from src.assessment import assess_ice_risk
from src.assessment.core import derive_explanation
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
    """Vorfall 2: Luft +1,2 °C, aber Oberfläche < 0 °C und Reif -> Eis erkannt.

    Reif heißt: Oberfläche unter dem Taupunkt (Schwellenwerte.md §0/§2:
    ΔT ≤ 0 ⇒ Kondensation/Reif ⇒ ROT). Die frühere Fassung nutzte ΔT=+0,2
    (Oberfläche ÜBER dem Taupunkt) und prüfte damit gar nicht das
    dokumentierte Frost-Szenario, sondern nur einen ORANGE-Randfall.
    """
    t_s = -1.0
    t_d = -0.5  # Oberfläche unter Taupunkt -> ΔT = -0.5 -> Reif/Kondensation -> ROT
    assert assess_ice_risk(t_s, t_d, thresholds) == RiskLevel.RED


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


def test_ungueltige_prognose_ist_gelb(thresholds):
    """NaN/inf in der Prognose -> defektes Forecasting -> konservativ GELB."""
    assert (
        assess_ice_risk(2.0, 0.0, thresholds, forecast_surface_temp_c=float("nan"))
        == RiskLevel.YELLOW
    )
    assert (
        assess_ice_risk(2.0, 0.0, thresholds, forecast_surface_temp_c=float("inf"))
        == RiskLevel.YELLOW
    )


def test_defekte_prognose_unterdrueckt_kein_rot(thresholds):
    """Eine kaputte Prognose (NaN/inf) darf eine akute ROT-Lage nicht auf GELB
    deklassieren (NF-01 Under-Alarm): die Ist-Bewertung hat Vorrang."""
    # T_s=-2.0, T_d=-1.0 ist fuer sich genommen ROT (gefroren + Kondensation).
    assert (
        assess_ice_risk(-2.0, -1.0, thresholds, forecast_surface_temp_c=float("nan"))
        == RiskLevel.RED
    )
    assert (
        assess_ice_risk(-2.0, -1.0, thresholds, forecast_surface_temp_c=float("inf"))
        == RiskLevel.RED
    )


def test_defekte_prognose_unterdrueckt_kein_orange(thresholds):
    """Eine kaputte Prognose (NaN/inf) darf eine ORANGE-Lage nicht auf GELB
    deklassieren: die Ist-Bewertung hat Vorrang vor dem defekten Subsystem."""
    # T_s=-1.0, T_d=-1.5 ist fuer sich genommen ORANGE (gefroren + feucht).
    assert (
        assess_ice_risk(-1.0, -1.5, thresholds, forecast_surface_temp_c=float("nan"))
        == RiskLevel.ORANGE
    )


# ---------------------------------------------------------------------------
# Reifpunkt-Korrektur unter 0 °C — konservativ (E-45 / DTB-69)
#
# Unter 0 °C ist fuer Reif die Saettigung ueber EIS massgeblich: der Reifpunkt
# T_f liegt ueber dem Wasser-Taupunkt T_d, also ist der reale Feuchte-Abstand
# ΔT_Reif = T_s - T_f kleiner als T_s - T_d. Die Kaskade nutzt deshalb bei
# T_s <= 0 °C die konservativere Referenz max(T_d, T_f). Das hebt das Risiko
# nur an, senkt es nie -> kann keinen neuen Miss und kein neues GRUEN erzeugen.
# ---------------------------------------------------------------------------


def test_reif_bei_sehr_kalter_oberflaeche_ist_orange_statt_gelb(thresholds):
    """Kaelte-Reif-Luecke: Reif-Beginn unter ~ -8 °C darf nicht auf GELB fallen.

    T_s=-10, T_d=-11,65: Wasser-ΔT=1,65 (>1,0 -> alt faelschlich GELB). Der
    Reifpunkt T_f≈-10,36 (> T_d) ergibt ΔT_Reif≈0,36 ≤ 1,0 -> Feuchte vorhanden
    -> ORANGE. Schliesst den systematischen Under-Alarm unter 0 °C (E-45).
    """
    assert assess_ice_risk(-10.0, -11.65, thresholds) == RiskLevel.ORANGE


def test_reif_onset_wird_konservativ_rot(thresholds):
    """Aktive Reif-Deposition: Oberflaeche am/unter dem Reifpunkt -> ROT.

    T_s=-10, T_d=-11,0: Wasser-ΔT=1,0 (alt: ORANGE). Der Reifpunkt T_f≈-9,77
    liegt UEBER T_s -> ΔT_Reif≈-0,23 ≤ 0 (Kondensation/Reif) -> ROT (E-45).
    """
    assert assess_ice_risk(-10.0, -11.0, thresholds) == RiskLevel.RED


def test_reifkorrektur_erzeugt_keinen_fehlalarm_bei_trockener_kaelte(thresholds):
    """Konservativ-Invariante (Gegenprobe): trockene Kaelte mit grossem Abstand
    bleibt GELB -- die Korrektur hebt nur, wo real Feuchte da ist, kein Fehlalarm.
    T_s=-10, T_d=-25: auch ΔT_Reif ≫ 1,0 -> nicht feucht -> GELB.
    """
    assert assess_ice_risk(-10.0, -25.0, thresholds) == RiskLevel.YELLOW


def test_derive_explanation_mit_nan_taupunkt_crasht_nicht(thresholds):
    """Selbst-Review E-45: die Reifpunkt-Referenz im Erklaertext darf bei einem
    NICHT-endlichen (NaN/inf) Taupunkt nicht crashen. assess_ice_risk liefert
    dann UNKNOWN; derive_explanation muss robust sensor_data zurueckgeben, nicht
    ueber frost_point_from_dew_point(NaN) einen ValueError werfen.
    """
    factor, expl = derive_explanation(
        -1.0, float("nan"), thresholds, None, RiskLevel.UNKNOWN, float("nan")
    )
    assert factor == "sensor_data"
    assert expl is not None
