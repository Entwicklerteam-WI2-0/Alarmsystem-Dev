"""Kern-Logik der Vereisungsbewertung (DTB-38).

Reine, zustandslose Funktion `assess_ice_risk`. Sie kennt keine Datenbank und keine
Netzwerk-Abhängigkeiten — alle Schwellen kommen aus der Config (NF-05, DTB-15).

Bewertungsmodell (priorisierte Kaskade, Schwellenwerte.md §2, E-34):
    ROT    -> T_s ≤ Gefrierpunkt  UND  ΔT ≤ Kondensation
    ORANGE -> T_s ≤ Gefrierpunkt  UND  Feuchte vorhanden (ΔT ≤ Feucht)
    GELB   -> T_s ≤ GELB-Auffang  ODER  Prognose T_s ≤ Gefrierpunkt
    GRUEN  -> sonst

Fail-safe (NF-01):
    * Fehlt der Taupunkt T_d, gilt Feuchte = wahr (konservativ).
    * Fehlende/veraltete oder ungültige (NaN/inf) Daten führen nie zu GRÜN.
    * Bei ungültigem T_s oder T_d wird `unknown` zurückgegeben.

Die Taupunkt-Berechnung selbst liegt in DTB-32; diese Funktion erwartet T_d
als berechneten Input. So bleiben Berechnung und Bewertung getrennt testbar.
"""

import math

from src.config.loader import Thresholds
from src.model.enums import RiskLevel


def assess_ice_risk(
    surface_temp_c: float,
    dew_point_c: float | None,
    thresholds: Thresholds,
    forecast_surface_temp_c: float | None = None,
) -> RiskLevel:
    """Bewertet das Vereisungsrisiko nach der priorisierten 4-Stufen-Kaskade.

    Args:
        surface_temp_c: Endliche Oberflächentemperatur T_s in °C.
        dew_point_c: Endlicher Taupunkt T_d in °C; None -> Feuchte unbestimmbar.
        thresholds: Geladene, validierte Schwellenwerte (DTB-15).
        forecast_surface_temp_c: Optionale Prognose-T_s für GELB-Vorwarnung.

    Returns:
        Die höchste zutreffende Risikostufe (ROT > ORANGE > GELB > GRÜN) oder
        `unknown`, wenn die Eingaben ungültig sind (NaN/inf) — nie GRÜN.
    """
    v = thresholds.vereisung
    p = thresholds.prognose

    # Fail-safe: ungültige (nicht-endliche) Eingaben -> unknown, nie GRÜN.
    if not math.isfinite(surface_temp_c):
        return RiskLevel.UNKNOWN
    if dew_point_c is not None and not math.isfinite(dew_point_c):
        return RiskLevel.UNKNOWN
    if forecast_surface_temp_c is not None and not math.isfinite(forecast_surface_temp_c):
        forecast_surface_temp_c = None

    # Feuchte-Vorhandensein: ΔT = T_s - T_d. Fehlt T_d -> konservativ wahr.
    if dew_point_c is None:
        humid = True
        delta_t: float | None = None
    else:
        delta_t = surface_temp_c - dew_point_c
        humid = delta_t <= v.delta_t_feucht_k

    # 1. ROT: gefrorene/feuchte Oberfläche unter/unmittelbar am Taupunkt.
    if (
        surface_temp_c <= v.t_s_gefrierpunkt_c
        and delta_t is not None
        and delta_t <= v.delta_t_kondensation_k
    ):
        return RiskLevel.RED

    # 2. ORANGE: gefrorene Oberfläche mit Feuchte (aber noch nicht am Taupunkt).
    if surface_temp_c <= v.t_s_gefrierpunkt_c and humid:
        return RiskLevel.ORANGE

    # 3. GELB: kalte/grenzwertige Oberfläche ODER Prognose droht Gefrieren.
    if surface_temp_c <= v.t_s_gelb_auffang_c:
        return RiskLevel.YELLOW
    if forecast_surface_temp_c is not None and forecast_surface_temp_c <= p.t_s_grenz_c:
        return RiskLevel.YELLOW

    # 4. GRÜN: alles andere — aber nur, wenn T_d bekannt ist.
    # Fehlt der Taupunkt, gilt Fail-safe (NF-01): nie GRÜN, mindestens GELB.
    if dew_point_c is None:
        return RiskLevel.YELLOW
    return RiskLevel.GREEN
