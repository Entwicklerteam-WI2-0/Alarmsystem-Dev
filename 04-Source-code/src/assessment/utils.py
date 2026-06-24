"""Hilfsfunktionen der Vereisungsbewertung (assessment).

Aktuell: Taupunktberechnung nach der Magnus-Formel (DTB-32).
Quelle der Parameter: Schwellenwerte.md §1 (a=17,62; b=243,12 °C).
"""

import math

# Magnus-Koeffizienten (Schwellenwerte.md §1): dimensionsloses a, b in °C.
# Gueltig fuer Wasser ueber dem Bereich -45 … +60 °C; Standardwerte nach Sonntag/WMO.
MAGNUS_A = 17.62
MAGNUS_B = 243.12

# Relative Feuchte ist physikalisch in (0, 100] %: bei 0 % ist der Taupunkt
# undefiniert (ln(0) -> -inf), ueber 100 % uebersaettigt und nicht plausibel.
MIN_HUMIDITY_PCT = 0.0
MAX_HUMIDITY_PCT = 100.0


def calculate_dew_point(air_temp_c: float, humidity_pct: float) -> float:
    """Berechnet den Taupunkt T_d (°C) aus Lufttemperatur und relativer Feuchte.

    Magnus-Formel mit Hilfsgroesse gamma:
        gamma = ln(RH/100) + (a * T_a) / (b + T_a)
        T_d   = (b * gamma) / (a - gamma)

    Args:
        air_temp_c: Lufttemperatur T_a in °C.
        humidity_pct: relative Luftfeuchte RH in Prozent, im Bereich (0, 100].

    Returns:
        Taupunkt T_d in °C (immer <= air_temp_c; Gleichheit bei RH = 100 %).

    Raises:
        ValueError: wenn humidity_pct nicht in (0, 100] liegt.
    """
    if not (MIN_HUMIDITY_PCT < humidity_pct <= MAX_HUMIDITY_PCT):
        raise ValueError(f"humidity_pct muss in (0, 100] liegen, erhalten: {humidity_pct}")

    gamma = math.log(humidity_pct / 100.0) + (MAGNUS_A * air_temp_c) / (MAGNUS_B + air_temp_c)
    return (MAGNUS_B * gamma) / (MAGNUS_A - gamma)
