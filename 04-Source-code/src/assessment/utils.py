"""Hilfsfunktionen der Vereisungsbewertung (assessment).

Aktuell: Taupunktberechnung nach der Magnus-Formel (DTB-32).
Quelle der Parameter: Schwellenwerte.md §1 (a=17,62; b=243,12 °C).
"""

import math

# Magnus-Koeffizienten (Schwellenwerte.md §1): dimensionsloses a, b in °C.
# Gueltig fuer Wasser im Bereich -45 … +60 °C; Standardwerte nach Sonntag/WMO.
MAGNUS_A = 17.62
MAGNUS_B = 243.12

# Magnus-Koeffizienten fuer die Saettigung ueber EIS (Sonntag/WMO): fuer den
# Reifpunkt T_f unter 0 °C (E-45). Der Saettigungsdampfdruck ueber Eis liegt unter
# dem ueber unterkuehltem Wasser -> der Reifpunkt liegt UEBER dem Wasser-Taupunkt
# (T_f >= T_d fuer T_d <= 0), der Feuchte-Abstand ΔT_Reif ist also kleiner.
MAGNUS_A_ICE = 22.46
MAGNUS_B_ICE = 272.62

# Relative Feuchte ist physikalisch in (0, 100] %: bei 0 % ist der Taupunkt
# undefiniert (ln(0) -> -inf), ueber 100 % uebersaettigt und nicht plausibel.
MIN_HUMIDITY_PCT = 0.0
MAX_HUMIDITY_PCT = 100.0

# Divisor zur Normierung der Prozent-Feuchte auf einen Anteil (0, 1].
PERCENT_DIVISOR = 100.0

# Magnus ist nur fuer T_a > -b definiert: am Pol -b wird der Divisor (b + T_a) null,
# UNTERHALB liefert die Formel ein still falsches (physikalisch unsinniges) Ergebnis,
# weil (b + T_a) negativ wird. Beides wird zurueckgewiesen (Fail-safe NF-01: kein
# stilles Ersatzergebnis). Die kleine Toleranz oberhalb -b faengt zusaetzlich die
# numerisch instabile Nahe-Pol-Zone (gerundete Nachbarwerte wie -243,120000000001).
POLE_TOLERANCE_C = 1e-9


def calculate_dew_point(air_temp_c: float, humidity_pct: float) -> float:
    """Berechnet den Taupunkt T_d (°C) aus Lufttemperatur und relativer Feuchte.

    Magnus-Formel mit Hilfsgroesse gamma:
        gamma = ln(RH/100) + (a * T_a) / (b + T_a)
        T_d   = (b * gamma) / (a - gamma)

    Args:
        air_temp_c: Lufttemperatur T_a in °C (endlich, > -b = -243,12 °C; am Pol
            und darunter ist die Magnus-Formel undefiniert).
        humidity_pct: relative Luftfeuchte RH in Prozent, im Bereich (0, 100].

    Returns:
        Taupunkt T_d in °C. Im Magnus-Gueltigkeitsbereich gilt T_d <= air_temp_c
        (Gleichheit bei RH = 100 %).

    Raises:
        ValueError: wenn humidity_pct nicht in (0, 100] liegt, air_temp_c nicht
            endlich ist (NaN/inf) oder air_temp_c <= -b (-243,12 °C) liegt
            (Magnus-Pol und darunter).

    Hinweis (Fail-safe, NF-01): Diese Funktion ist ein reiner Rechner und liefert
    bewusst KEIN stilles Ersatzergebnis. Der Aufrufer (DTB-60 Poller) MUSS den
    ValueError fangen und den fehlenden Taupunkt als "unbestimmbar" behandeln
    (dew_point_c=None), damit die Bewertung (DTB-38) konservativ >= GELB einstuft
    und nie faelschlich GRUEN ausgibt. Physikalische Plausibilitaet/Bereichsgrenzen
    (realistische Temperaturspanne) prueft die vorgelagerte Validierungsschicht,
    nicht dieser Rechner.
    """
    if not (MIN_HUMIDITY_PCT < humidity_pct <= MAX_HUMIDITY_PCT):
        raise ValueError(f"humidity_pct muss in (0, 100] liegen, erhalten: {humidity_pct}")

    if not math.isfinite(air_temp_c):
        raise ValueError(f"air_temp_c muss endlich sein, erhalten: {air_temp_c}")

    if air_temp_c <= -MAGNUS_B + POLE_TOLERANCE_C:
        raise ValueError(
            f"air_temp_c muss > -{MAGNUS_B} °C sein (am Magnus-Pol oder darunter "
            f"ist die Formel undefiniert), erhalten: {air_temp_c}"
        )

    gamma = math.log(humidity_pct / PERCENT_DIVISOR) + (MAGNUS_A * air_temp_c) / (
        MAGNUS_B + air_temp_c
    )
    return (MAGNUS_B * gamma) / (MAGNUS_A - gamma)


def frost_point_from_dew_point(dew_point_c: float) -> float:
    """Berechnet den Reifpunkt T_f (°C) aus dem Wasser-Taupunkt T_d (E-45).

    T_d und T_f gehoeren zum GLEICHEN Dampfdruck e, nur bezueglich anderer
    Saettigungskurven (Wasser bzw. Eis). Aus der Wasserkurve laesst sich der
    dimensionslose Term gamma = ln(e/e0) direkt aus T_d gewinnen und in die
    Eiskurve invertieren -- ohne T_a/RH erneut zu brauchen:

        gamma = a_w * T_d / (b_w + T_d)          # aus e_water(T_d)
        T_f   = gamma * b_i / (a_i - gamma)      # Inversion von e_ice(T_f)=e

    Unter 0 °C gilt T_f >= T_d (Saettigung ueber Eis < ueber Wasser), bei 0 °C
    fallen beide Kurven zusammen (T_f = T_d = 0). Der Aufrufer nutzt daher unter
    dem Gefrierpunkt max(T_d, T_f) als konservative Feuchte-Referenz (nie weniger
    Risiko als der Wasser-Taupunkt).

    Args:
        dew_point_c: Wasser-Taupunkt T_d in °C (endlich).

    Returns:
        Reifpunkt T_f in °C.

    Raises:
        ValueError: wenn dew_point_c nicht endlich ist (NaN/inf) -- kein stilles
            Ersatzergebnis (Fail-safe NF-01, konsistent mit calculate_dew_point).

    Hinweis: Fuer jeden von calculate_dew_point erzeugten (endlichen, > -b_w)
    Taupunkt ist gamma < a_w < a_i, der Nenner (a_i - gamma) also stets positiv
    -- kein Pol im real erreichbaren Wertebereich.
    """
    if not math.isfinite(dew_point_c):
        raise ValueError(f"dew_point_c muss endlich sein, erhalten: {dew_point_c}")

    gamma = (MAGNUS_A * dew_point_c) / (MAGNUS_B + dew_point_c)
    return (gamma * MAGNUS_B_ICE) / (MAGNUS_A_ICE - gamma)
