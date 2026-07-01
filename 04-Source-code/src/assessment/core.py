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
    * Eine defekte (NaN/inf) Prognose wird erst NACH der ROT/ORANGE-Kaskade
      geprüft -> mindestens GELB, ohne eine akute Ist-Lage zu deklassieren.

Die Taupunkt-Berechnung selbst liegt in DTB-32; diese Funktion erwartet T_d
als berechneten Input. So bleiben Berechnung und Bewertung getrennt testbar.
"""

import math

from src.assessment.utils import frost_point_from_dew_point
from src.config.loader import Thresholds
from src.model.enums import RiskLevel

# Wire-Contract-Grenzen (AssessmentCurrent, API_FROZEN_v1): driving_factor <= 64,
# explanation <= 512. Pydantic erzwingt sie hart (ValidationError) -> Texte defensiv
# kappen, damit eine kuenftige laengere Begruendung nie einen 500 ausloest (DTB-66).
MAX_DRIVING_FACTOR_LEN = 64
MAX_EXPLANATION_LEN = 512

# Geschlossene Menge der driving_factor-Werte (kein Magic String, eine Quelle der
# Wahrheit fuer Kaskade UND Fail-safe-Pfade in service.py).
DRIVING_FACTOR_DEW_POINT = "dew_point"
DRIVING_FACTOR_SURFACE_TEMP = "surface_temp"
DRIVING_FACTOR_FORECAST = "forecast"
DRIVING_FACTOR_STALE = "stale"
DRIVING_FACTOR_SENSOR_FAULT = "sensor_fault"
# Ungueltiger (NaN/inf) Mess-/Taupunktwert: assess_ice_risk liefert UNKNOWN, ohne
# dass Stale/Fault griff -> eigener Faktor fuer Observability (NF-01-Geist, DTB-66).
DRIVING_FACTOR_SENSOR_DATA = "sensor_data"
# Anzeige-Hysterese haelt eine andere Stufe als die rohe Bewertung (displayed != roh, DTB-27):
# eigener Faktor, damit der Serve-Text die gehaltene Stufe erklaeren kann, ohne die rohen
# Messwerte in eine widerspruechliche Ungleichung zu rendern (Audit-Haertung #4).
DRIVING_FACTOR_HYSTERESE = "anzeige_hysterese"

# Fail-fast beim Import: jeder geschlossene driving_factor-Wert MUSS in den
# Wire-Contract passen (<= 64 Zeichen, AssessmentCurrent). service.py setzt die
# Werte via pydantic model_copy(update=...), das KEINE erneute max_length-
# Validierung ausfuehrt -> ein zu langer Wert wuerde erst beim Wire-Serialisieren
# als 500 auffallen. Dieser Modul-Level-Guard schlaegt stattdessen sofort beim
# Laden des Moduls an und faengt eine versehentlich zu lange neue Konstante ab
# (DTB-66 Review LOW).
_DRIVING_FACTOR_VALUES = (
    DRIVING_FACTOR_DEW_POINT,
    DRIVING_FACTOR_SURFACE_TEMP,
    DRIVING_FACTOR_FORECAST,
    DRIVING_FACTOR_STALE,
    DRIVING_FACTOR_SENSOR_FAULT,
    DRIVING_FACTOR_SENSOR_DATA,
    DRIVING_FACTOR_HYSTERESE,
)
assert all(len(factor) <= MAX_DRIVING_FACTOR_LEN for factor in _DRIVING_FACTOR_VALUES), (
    "DRIVING_FACTOR_*-Konstante ueberschreitet die Wire-Contract-Grenze "
    f"(<= {MAX_DRIVING_FACTOR_LEN} Zeichen): "
    + ", ".join(f"{f!r}={len(f)}" for f in _DRIVING_FACTOR_VALUES)
)


def _humidity_reference_c(
    surface_temp_c: float, dew_point_c: float, thresholds: Thresholds
) -> float:
    """Konservative Feuchte-Referenz fuer den ΔT der Kaskade (E-45).

    Unter dem Gefrierpunkt (T_s <= t_s_gefrierpunkt_c) ist fuer Reif die
    Saettigung ueber EIS massgeblich -> der Reifpunkt T_f (>= Wasser-Taupunkt T_d)
    ist die richtige Referenz. `max(T_d, T_f)` garantiert, dass die abgeleitete
    ΔT = T_s - Referenz nie GROESSER ist als T_s - T_d: die Korrektur hebt das
    Risiko nur an, senkt es nie (kein neuer Miss, kein neues GRUEN moeglich).

    Oberhalb des Gefrierpunkts (keine Reif-Deposition; fluessige Kondensation /
    gefrierender Regen -> Klareis) bleibt der Wasser-Taupunkt die korrekte Kurve.
    `dew_point_c` muss endlich sein (der Aufrufer garantiert das).
    """
    if surface_temp_c <= thresholds.vereisung.t_s_gefrierpunkt_c:
        return max(dew_point_c, frost_point_from_dew_point(dew_point_c))
    return dew_point_c


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

    # Feuchte-Vorhandensein: ΔT = T_s - Feuchte-Referenz. Fehlt T_d -> konservativ wahr.
    # Unter 0 °C ist die Referenz der Reifpunkt statt des Wasser-Taupunkts (E-45),
    # sonst der Taupunkt selbst -> konservativer (nie weniger Risiko).
    if dew_point_c is None:
        humid = True
        delta_t: float | None = None
    else:
        delta_t = surface_temp_c - _humidity_reference_c(surface_temp_c, dew_point_c, thresholds)
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

    # Defekte Prognose (NaN/inf): erst HIER prüfen, NACH ROT/ORANGE. Ein kaputtes
    # Forecasting-Subsystem darf eine akute Ist-Lage (ROT/ORANGE) nicht auf GELB
    # deklassieren (NF-01 Under-Alarm). Liegt keine ROT/ORANGE-Lage vor, reagiert
    # es konservativ mit GELB (nie GRÜN). Ein None-Wert bedeutet „keine Prognose
    # verfügbar" und bleibt ohne Auswirkung auf die Bewertung.
    if forecast_surface_temp_c is not None and not math.isfinite(forecast_surface_temp_c):
        return RiskLevel.YELLOW

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


def derive_explanation(
    surface_temp_c: float,
    dew_point_c: float | None,
    thresholds: Thresholds,
    forecast_surface_temp_c: float | None,
    risk_level: RiskLevel,
    delta_t: float | None,
) -> tuple[str | None, str | None]:
    """Leitet driving_factor und explanation aus dem Bewertungsergebnis ab (DTB-66).

    Gibt (driving_factor, explanation) zurueck. Spiegelt die Kaskade aus
    assess_ice_risk (inkl. der Forecast-Schwellenpruefung) um das bereits
    bestimmte risk_level herum, ohne sie zu duplizieren.

    UNKNOWN aus dieser Funktion deckt nur den Happy-Pfad-Fall ab, in dem
    assess_ice_risk wegen ungueltiger (NaN/inf) Sensorwerte UNKNOWN liefert
    -> driving_factor=sensor_data. Die Stale-/Fault-/Keine-Daten-UNKNOWN-Faelle
    werden VOR dem Aufruf in service.py gesetzt und erreichen diese Funktion nicht.

    Args:
        surface_temp_c: Endliche Oberflaechentemperatur T_s.
        dew_point_c: Endlicher Taupunkt T_d oder None (unbestimmbar).
        thresholds: Schwellenwerte (aus Config, NF-05).
        forecast_surface_temp_c: Optionale 30-min-T_s-Prognose.
        risk_level: Bereits durch assess_ice_risk bestimmte Stufe.
        delta_t: T_s - T_d (vorberechnet); None wenn dew_point_c None ist.

    Returns:
        (driving_factor, explanation): Felder fuer das Assessment/Wire-Modell.
        Laengen respektieren die Wire-Contract-Grenzen (max 64 / 512 Zeichen).
    """
    v = thresholds.vereisung
    p = thresholds.prognose

    # ΔT im Text auf DERSELBEN Feuchte-Referenz wie die Klassifikation (E-45):
    # unter 0 °C der Reifpunkt-Abstand, sonst der Taupunkt-Abstand. Sonst widerspraeche
    # der angezeigte Wert der Stufe (z. B. ORANGE trotz Wasser-ΔT > 1,0). Das Wire-Feld
    # `delta_t` (service.py) bleibt separat der reine Wasser-Taupunkt-Abstand (Contract).
    # isfinite-Guard: bei NaN/inf-Taupunkt (assess_ice_risk -> UNKNOWN) wuerde
    # frost_point_from_dew_point einen ValueError werfen -> hier nicht recomputen.
    if dew_point_c is not None and math.isfinite(dew_point_c):
        delta_t = surface_temp_c - _humidity_reference_c(surface_temp_c, dew_point_c, thresholds)

    if risk_level is RiskLevel.RED:
        dt_str = f"{delta_t:.1f} K" if delta_t is not None else "–"
        expl = (
            f"Aktive Eisbildung: Oberfläche {surface_temp_c:.1f} °C "
            f"≤ {v.t_s_gefrierpunkt_c:.1f} °C, ΔT={dt_str} "
            f"(Kondensation/Reif)."
        )
        return _cap_factor(DRIVING_FACTOR_DEW_POINT), _cap_expl(expl)

    if risk_level is RiskLevel.ORANGE:
        if dew_point_c is None:
            expl = (
                f"Vereisung wahrscheinlich: Oberfläche {surface_temp_c:.1f} °C "
                f"≤ {v.t_s_gefrierpunkt_c:.1f} °C, Taupunkt unbestimmbar "
                f"(Fail-safe: Feuchte angenommen)."
            )
            return _cap_factor(DRIVING_FACTOR_SURFACE_TEMP), _cap_expl(expl)
        dt_str = f"{delta_t:.1f} K" if delta_t is not None else "–"
        expl = (
            f"Vereisung wahrscheinlich: Oberfläche {surface_temp_c:.1f} °C "
            f"≤ {v.t_s_gefrierpunkt_c:.1f} °C, ΔT={dt_str} (Feuchte vorhanden)."
        )
        return _cap_factor(DRIVING_FACTOR_DEW_POINT), _cap_expl(expl)

    if risk_level is RiskLevel.YELLOW:
        # Bewusste Abweichung von assess_ice_risk's interner Pruefreihenfolge:
        # dort wird die defekte-Prognose-Pruefung VOR dem GELB-Auffang (T_s kalt)
        # ausgewertet; hier spiegeln wir die Prioritaet fuer den OPERATOR um —
        # surface_temp vor forecast vor T_d-Fail-safe. Grund: ist die Oberflaeche
        # tatsaechlich kalt (<= t_s_gelb_auffang_c), ist das die unmittelbar
        # entscheidungsrelevante Ist-Lage, unabhaengig davon, ob das
        # Forecasting-Subsystem daneben kaputt ist. assess_ice_risk liefert in
        # beiden Faellen GELB (Ergebnis korrekt); nur der angezeigte treibende
        # Faktor wuerde im Randfall "T_s kalt UND Prognose defekt" abweichen
        # (surface_temp statt forecast). Das ist ein bewusst gewaehlter Trade-off
        # zugunsten der Ist-Lage (DTB-66 Review MEDIUM).
        if surface_temp_c <= v.t_s_gelb_auffang_c:
            expl = (
                f"Grenzwertiger Bereich: Oberfläche {surface_temp_c:.1f} °C "
                f"≤ {v.t_s_gelb_auffang_c:.1f} °C (kalt/grenzwertig)."
            )
            return _cap_factor(DRIVING_FACTOR_SURFACE_TEMP), _cap_expl(expl)
        if forecast_surface_temp_c is not None:
            # Defekte (NaN/inf) Prognose stuft assess_ice_risk konservativ auf GELB
            # (core.py-Guard) -> hier KEINEN numerischen Wert formatieren, sonst leakt
            # "nan"/"inf" in den operatorsichtbaren Text (DTB-66 Review).
            if not math.isfinite(forecast_surface_temp_c):
                return _cap_factor(DRIVING_FACTOR_FORECAST), _cap_expl(
                    "Prognosedaten defekt, Fail-safe: GELB-Vorwarnung."
                )
            # Schwellenpruefung wie in assess_ice_risk spiegeln: nur wenn die Prognose
            # tatsaechlich Gefrieren droht (forecast <= t_s_grenz_c), ist sie der
            # treibende Faktor. Sonst kam GELB ueber den T_d-Fail-safe (dew=None) und
            # wir fallen durch -> sonst widerspruechlicher Text "5.0 ≤ 0.0" (DTB-66 Review).
            if forecast_surface_temp_c <= p.t_s_grenz_c:
                expl = (
                    f"30-min-Prognose: T_s prognostiziert {forecast_surface_temp_c:.1f} °C "
                    f"≤ {p.t_s_grenz_c:.1f} °C (Vorwarnung)."
                )
                return _cap_factor(DRIVING_FACTOR_FORECAST), _cap_expl(expl)
        # Fail-safe: T_d unbestimmbar, T_s > GELB-Auffang -> nie GRUEN.
        expl = "Taupunkt unbestimmbar, Fail-safe: keine GRÜN-Freigabe."
        return _cap_factor(DRIVING_FACTOR_DEW_POINT), _cap_expl(expl)

    if risk_level is RiskLevel.UNKNOWN:
        # Happy-Pfad-UNKNOWN: assess_ice_risk hat wegen ungueltiger (NaN/inf)
        # Sensor-/Taupunktwerte UNKNOWN geliefert. Observability statt leerer Felder.
        return _cap_factor(DRIVING_FACTOR_SENSOR_DATA), _cap_expl(
            "Fail-safe: Sensorwert ungültig (NaN/inf)."
        )

    # GREEN: kein driving_factor aus dieser Funktion.
    return None, None


def _cap_expl(text: str) -> str:
    """Kappt eine explanation defensiv auf die Wire-Contract-Grenze (DTB-66)."""
    return text[:MAX_EXPLANATION_LEN]


def _cap_factor(factor: str) -> str:
    """Kappt einen driving_factor defensiv auf die Wire-Contract-Grenze (DTB-66)."""
    return factor[:MAX_DRIVING_FACTOR_LEN]
