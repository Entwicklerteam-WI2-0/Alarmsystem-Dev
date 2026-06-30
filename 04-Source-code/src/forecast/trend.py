"""30-min-T_s-Trendprognose (DTB-33, FA-06) — reine lineare Extrapolation.

Backend-Konzept §8 / Schwellenwerte.md §2 (Z. 42/103): Aus der T_s-Zeitreihe wird
per linearer Regression die Oberflaechentemperatur `horizon_min` Minuten voraus
projiziert. Der einzige Konsument ist `assess_ice_risk(forecast_surface_temp_c=...)`
(GELB-Vorwarnung, wenn die Prognose `<= t_s_grenz_c`).

Bewusst eine REINE Funktion (DB-frei, keine Netzwerk-/Zeit-Seiteneffekte): die
Zeitreihe wird uebergeben, damit der Trend voll unit-testbar bleibt. Das Lesen der
Reihe aus dem Repository uebernimmt die Bruecke `forecast.bridge`.

Fail-safe (NF-01): bei zu duenner oder entarteter Datenlage liefert die Funktion
`None` ("keine Prognose"). None senkt die Risikostufe nie ab — die Basiskaskade
bewertet weiter auf dem Ist-Wert; die Prognose kann nur GELB ergaenzen.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime, timedelta

from src.model.schemas import Reading

# Untergrenze fuer die Zeitvarianz sxx (in Minuten^2). Liegt die Varianz darunter,
# gilt die Regression als numerisch entartet (nahezu identische Timestamps) ->
# fail-safe None, statt eine ausufernde Steigung zu extrapolieren. 1e-9 Min^2
# entspricht ca. 2 ms Zeitspanne bei zwei Punkten, also weit unter realer G1-Kadenz.
_MIN_SXX = 1e-9


def forecast_surface_temp(
    readings: Sequence[Reading],
    now: datetime,
    *,
    horizon_min: float,
    window_min: float,
    min_points: int,
    min_forecast_temp_c: float,
) -> float | None:
    """Projiziert T_s per linearer Regression `horizon_min` Minuten voraus.

    Args:
        readings: Readings desselben Sensors (beliebige Reihenfolge).
        now: Bezugszeitpunkt (UTC, zeitzonenbewusst); x = 0 der Regression.
        horizon_min: Prognosehorizont in Minuten (FA-06: 30).
        window_min: Trendfenster in Minuten; nur Readings mit
            `now - window_min <= measured_at <= now` gehen ein.
        min_points: Mindestanzahl gueltiger (endlicher) Stuetzstellen.
        min_forecast_temp_c: Physikalische Untergrenze fuer die Prognose (°C).
            Eine lineare Extrapolation ueber steile/kuenstliche Rampen kann sonst
            unter den realen Messbereich laufen (z. B. -50.2 °C). Der Wert wird
            nach unten geclampt, ohne die GELB-Vorwarnung zu deaktivieren.

    Returns:
        Die extrapolierte (und nach unten geclampfte) Oberflächentemperatur
        (float) oder `None`, wenn kein belastbarer Trend bestimmbar ist (zu
        wenige Punkte, keine Zeitvarianz, nicht-endliches Ergebnis).

    Raises:
        ValueError: Wenn `now` nicht zeitzonenbewusst ist (UTC).
    """
    if now.tzinfo is None:
        raise ValueError("now muss zeitzonenbewusst sein (UTC)")
    if not math.isfinite(min_forecast_temp_c):
        # Defekte Untergrenze -> keine Prognose liefern (NF-01), statt mit
        # unklarem Clamp weiterzurechnen.
        return None

    points = _collect_points(readings, now, window_min)
    if len(points) < min_points:
        return None

    return _project(points, horizon_min, min_forecast_temp_c)


def _collect_points(
    readings: Sequence[Reading], now: datetime, window_min: float
) -> list[tuple[float, float]]:
    """Filtert auf das Zeitfenster + endliche T_s und gibt (x, y)-Paare zurueck.

    x = Minuten relativ zu `now` (negativ in der Vergangenheit) — relative Zeit
    statt Epoch-Sekunden haelt die Regression numerisch stabil.
    """
    cutoff = now - timedelta(minutes=window_min)
    points: list[tuple[float, float]] = []
    for reading in readings:
        # Zeitfenster-Filter (bewusste Doppelfilterung mit bridge.py: die Bruecke
        # begrenzt die DB-Abfrage, diese Funktion garantiert die Semantik von
        # `window_min` fuer alle Aufrufer, auch wenn readings ausserhalb kommen).
        # `> now` ist zusaetzlich ein Clock-Skew-Guard: laeuft die G1-Uhr G2 vor,
        # kann measured_at in der Zukunft liegen. Solche Punkte werden verworfen.
        # Fail-safe: schlimmstenfalls bleiben < min_points uebrig -> None (kein Under-Alarm).
        if reading.measured_at < cutoff or reading.measured_at > now:
            continue
        y = reading.surface_temp_c
        if not math.isfinite(y):
            continue
        x = (reading.measured_at - now).total_seconds() / 60.0
        points.append((x, y))
    return points


def _project(
    points: list[tuple[float, float]], horizon_min: float, min_forecast_temp_c: float
) -> float | None:
    """Least-squares-Gerade durch die Punkte, ausgewertet bei x = +horizon_min."""
    n = len(points)
    mean_x = sum(x for x, _ in points) / n
    mean_y = sum(y for _, y in points) / n
    sxx = sum((x - mean_x) ** 2 for x, _ in points)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in points)
    # sxx ist Summe von Quadraten -> >= 0. Liegt es exakt bei 0.0 oder nur
    # numerisch knapp darueber (nahezu identische Timestamps), ist die Regression
    # entartet -> fail-safe None, statt eine ausufernde Steigung zu extrapolieren.
    # math.isfinite(forecast) fängt zudem NaN/inf bei entarteten Zahlen ab.
    if sxx < _MIN_SXX:
        return None
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x  # y bei x = 0 (= now)
    forecast = intercept + slope * horizon_min  # x = +horizon_min (now + horizon)
    if not math.isfinite(forecast):
        return None
    # Physikalische Untergrenze: bei steilen/kuenstlichen Rampen (z. B. Test-
    # Datensaetze) kann die Gerade unter den realen Messbereich laufen. Nach
    # unten clampln statt unplausible Werte durchzureichen (FA-06/NF-01).
    return max(forecast, min_forecast_temp_c)
