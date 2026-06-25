"""Hilfsfunktionen der Vereisungsbewertung (assessment).

Aktuell: Taupunktberechnung nach der Magnus-Formel (DTB-32).
Quelle der Parameter: Schwellenwerte.md §1 (a=17,62; b=243,12 °C).
"""

import math

# Magnus-Koeffizienten (Schwellenwerte.md §1): dimensionsloses a, b in °C.
# Gueltig fuer Wasser im Bereich -45 … +60 °C; Standardwerte nach Sonntag/WMO.
MAGNUS_A = 17.62
MAGNUS_B = 243.12

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
