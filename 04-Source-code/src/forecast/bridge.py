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
        prognose: Geladene Prognose-Schwellen (Fenster, Horizont, min_points).
        now: Bezugszeitpunkt (UTC, zeitzonenbewusst).

    Returns:
        Die extrapolierte Oberflaechentemperatur oder None (keine belastbare Prognose).

    Raises:
        ValueError: Wenn `now` naiv (nicht zeitzonenbewusst) ist. Bewusst NICHT
            abgefangen: ein naives `now` ist ein Programmierfehler, kein transienter
            Datenlayer-Fehler — der Scheduler soll ihn sichtbar machen, statt ihn
            als "keine Prognose" zu maskieren. Nur `RepositoryError` ist fail-safe.
    """
    if reading is None:
        return None

    since = now - timedelta(minutes=prognose.trend_window_min)
    try:
        readings = reading_repo.get_since(reading.sensor_id, since)
    except RepositoryError as exc:
        logger.error("Prognose: Zeitreihe nicht lesbar (fail-safe, keine Prognose): %s", exc)
        return None

    return forecast_surface_temp(
        readings,
        now,
        horizon_min=prognose.horizon_min,
        window_min=prognose.trend_window_min,
        min_points=prognose.min_points,
    )
