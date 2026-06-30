"""Forecast-Bruecke (DTB-33): liest die T_s-Zeitreihe und ruft den reinen Producer.

Trennt I/O (Repository-Zugriff) von der reinen Trend-Mathematik (`forecast.trend`):
der Scheduler (main.py) ruft pro Zyklus nur diese eine Funktion, statt selbst die
DB zu lesen — so bleibt main.py schlank und die Logik testbar (Backend-Konzept §8:
"forecast/ liest die Zeitreihe").

Fail-safe (NF-01): kein Reading (fehlgeschlagener Poll) oder ein Repository-Fehler
fuehren zu None ("keine Prognose"). None senkt die Risikostufe nie ab — die
Basiskaskade bewertet auf dem Ist-Wert weiter; die Prognose kann nur GELB ergaenzen.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from src.config.loader import PrognoseSchwellen
from src.forecast.trend import forecast_surface_temp
from src.model.schemas import Reading
from src.storage.repository import Repository, RepositoryError

logger = logging.getLogger(__name__)


def compute_forecast_for_cycle(
    reading: Reading | None,
    reading_repo: Repository,
    prognose: PrognoseSchwellen,
    now: datetime,
) -> float | None:
    """Berechnet die 30-min-T_s-Prognose fuer einen Bewertungszyklus.

    Args:
        reading: Das frisch gepollte Reading (liefert die sensor_id) oder None bei
            fehlgeschlagenem Poll -> dann keine Prognose (Fail-safe).
        reading_repo: Repository fuer die Reading-Historie (get_since).
        prognose: Geladene Prognose-Schwellen (Fenster, Horizont, min_points,
            physikalische Untergrenze).
        now: Bezugszeitpunkt (UTC, zeitzonenbewusst).

    Returns:
        Die extrapolierte (und nach unten geclampfte) Oberflächentemperatur oder
        None (keine belastbare Prognose).

    Raises:
        ValueError: Wenn `now` naiv (nicht zeitzonenbewusst) ist. Ein naives `now`
            ist ein Programmierfehler, kein transienter Datenlayer-Fehler. Die
            Funktion wirft daher bewusst einen ValueError; der Scheduler in
            `main.py` fängt diesen (und alle anderen unerwarteten Fehler) in seinem
            `except Exception`-Block ab, loggt ihn sichtbar und setzt
            `forecast = None`, damit die Bewertung unbedingt weiterläuft (NF-01).
            Nur `RepositoryError` wird innerhalb der Brücke als fail-safe behandelt.
    """
    if reading is None:
        return None

    # DB-Last-Begrenzung: nur Readings innerhalb des Trendfensters holen.
    # `forecast_surface_temp` fuehrt denselben Fenster-Filter nochmals durch
    # (Defense-in-Depth): die Bruecke begrenzt die DB-Abfrage, die reine
    # Trend-Funktion garantiert die API-Semantik fuer jeden Aufrufer.
    since = now - timedelta(minutes=prognose.trend_window_min)
    try:
        readings = reading_repo.get_since(
            reading.sensor_id, since, limit=prognose.max_readings_limit
        )
    except RepositoryError as exc:
        logger.error("Prognose: Zeitreihe nicht lesbar (fail-safe, keine Prognose): %s", exc)
        return None

    # Invariante (bewusst NICHT abgefangen): forecast_surface_temp subtrahiert `now` von
    # `reading.measured_at`. Beide sind zeitzonenbewusst — `now` per ValueError-Guard in
    # trend.py, `measured_at` weil das Pydantic-`Reading`-Schema UTC-aware erzwingt. Faellt
    # diese Schema-Invariante je weg, wuerde die Subtraktion einen TypeError werfen; der bleibt
    # bewusst sichtbar (Programmier-/Contract-Fehler), statt als "keine Prognose" maskiert
    # zu werden. Nur transiente Datenlayer-Fehler (RepositoryError) sind fail-safe.
    return forecast_surface_temp(
        readings,
        now,
        horizon_min=prognose.horizon_min,
        window_min=prognose.trend_window_min,
        min_points=prognose.min_points,
        min_forecast_temp_c=prognose.min_forecast_temp_c,
    )
