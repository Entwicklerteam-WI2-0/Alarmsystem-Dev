"""Tests fuer den 30-min-T_s-Prognose-Producer (DTB-33, FA-06).

Reine Funktion `forecast_surface_temp`: lineare Regression ueber die T_s-Zeitreihe
und Extrapolation `horizon_min` Minuten voraus. Fail-safe-Verhalten (NF-01):
bei zu duenner/entarteter Datenlage liefert sie None ("keine Prognose"), nie einen
geratenen Wert.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from src.forecast.trend import forecast_surface_temp
from src.model.schemas import Reading

_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
_HORIZON_MIN = 30.0
_WINDOW_MIN = 30.0
_MIN_POINTS = 3
_MIN_FORECAST_TEMP_C = -50.0


def _reading(minutes_ago: float, surface: float) -> Reading:
    """Baut ein Reading mit measured_at = _NOW - minutes_ago (uebrige Felder irrelevant)."""
    ts = _NOW - timedelta(minutes=minutes_ago)
    return Reading(
        sensor_id="anr-rwy-01",
        measured_at=ts,
        surface_temp_c=surface,
        air_temp_c=surface + 1.0,
        humidity_pct=80.0,
        received_at=ts,
    )


def test_fallender_trend_projiziert_unter_null():
    # T_s faellt linear (2.0 -> 1.0 -> 0.0 ueber 20 min) -> Steigung -0.1/min
    # -> in 30 min: 0.0 + (-0.1 * 30) = -3.0 (<= 0 -> GELB-Vorwarnung beim Consumer).
    readings = [_reading(20, 2.0), _reading(10, 1.0), _reading(0, 0.0)]
    forecast = forecast_surface_temp(
        readings,
        _NOW,
        horizon_min=_HORIZON_MIN,
        window_min=_WINDOW_MIN,
        min_points=_MIN_POINTS,
        min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
    )
    assert forecast is not None
    assert forecast == pytest.approx(-3.0)


def test_flacher_warmer_trend_bleibt_positiv():
    # Konstante warme Oberflaeche -> Steigung 0 -> Prognose = Niveau (5.0 > 0).
    readings = [_reading(20, 5.0), _reading(10, 5.0), _reading(0, 5.0)]
    forecast = forecast_surface_temp(
        readings,
        _NOW,
        horizon_min=_HORIZON_MIN,
        window_min=_WINDOW_MIN,
        min_points=_MIN_POINTS,
        min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
    )
    assert forecast == pytest.approx(5.0)


def test_zu_wenige_punkte_keine_prognose():
    readings = [_reading(10, 1.0), _reading(0, 0.0)]  # nur 2 < min_points=3
    assert (
        forecast_surface_temp(
            readings,
            _NOW,
            horizon_min=_HORIZON_MIN,
            window_min=_WINDOW_MIN,
            min_points=_MIN_POINTS,
            min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
        )
        is None
    )


def test_alle_gleicher_zeitstempel_keine_prognose():
    # Keine Zeitvarianz -> Steigung unbestimmbar -> None (kein Rateversuch).
    readings = [_reading(0, 1.0), _reading(0, 2.0), _reading(0, 3.0)]
    assert (
        forecast_surface_temp(
            readings,
            _NOW,
            horizon_min=_HORIZON_MIN,
            window_min=_WINDOW_MIN,
            min_points=_MIN_POINTS,
            min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
        )
        is None
    )


def test_nahezu_gleicher_zeitstempel_ist_entartet():
    # Mikrosekunden-Abstand zwischen den Stuetzstellen -> sxx winzig, aber nicht 0.0.
    # Ohne epsilon-Guard wuerde eine enorme, aber endliche Steigung durchgereicht.
    readings = [
        _reading(0.0, 1.0),
        _reading(1e-7, 2.0),  # ~6 µs vor _NOW
        _reading(2e-7, 3.0),  # ~12 µs vor _NOW
    ]
    assert (
        forecast_surface_temp(
            readings,
            _NOW,
            horizon_min=_HORIZON_MIN,
            window_min=_WINDOW_MIN,
            min_points=_MIN_POINTS,
            min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
        )
        is None
    )


def test_nicht_endliche_werte_werden_gefiltert():
    # NaN-Stuetzstelle wird verworfen; die 3 endlichen reichen -> endliche Prognose.
    bad = _reading(15, float("nan"))
    readings = [_reading(20, 2.0), bad, _reading(10, 1.0), _reading(0, 0.0)]
    forecast = forecast_surface_temp(
        readings,
        _NOW,
        horizon_min=_HORIZON_MIN,
        window_min=_WINDOW_MIN,
        min_points=_MIN_POINTS,
        min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
    )
    assert forecast is not None
    assert math.isfinite(forecast)
    assert forecast == pytest.approx(-3.0)


def test_unsortierte_readings_liefern_gleiches_ergebnis():
    readings = [_reading(0, 0.0), _reading(20, 2.0), _reading(10, 1.0)]  # gemischt
    forecast = forecast_surface_temp(
        readings,
        _NOW,
        horizon_min=_HORIZON_MIN,
        window_min=_WINDOW_MIN,
        min_points=_MIN_POINTS,
        min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
    )
    assert forecast == pytest.approx(-3.0)


def test_readings_ausserhalb_des_fensters_ignoriert():
    # Ein altes Reading (40 min) liegt vor dem 30-min-Fenster -> wird ignoriert;
    # die 3 Punkte im Fenster bleiben uebrig -> Trend wie gehabt.
    readings = [_reading(40, 99.0), _reading(20, 2.0), _reading(10, 1.0), _reading(0, 0.0)]
    forecast = forecast_surface_temp(
        readings,
        _NOW,
        horizon_min=_HORIZON_MIN,
        window_min=_WINDOW_MIN,
        min_points=_MIN_POINTS,
        min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
    )
    assert forecast == pytest.approx(-3.0)


def test_zukunfts_reading_clock_skew_wird_ignoriert():
    # Clock-Skew: G1-Uhr laeuft G2 vor -> measured_at > now. Das frischeste (zukuenftige)
    # Reading wird verworfen (trend.py: measured_at > now -> continue), nie ein Punkt aus
    # der Zukunft. Die 3 Punkte im Fenster bleiben -> Trend unveraendert (-3.0).
    future = _reading(-2, 99.0)  # 2 min NACH now (measured_at > _NOW)
    readings = [future, _reading(20, 2.0), _reading(10, 1.0), _reading(0, 0.0)]
    forecast = forecast_surface_temp(
        readings,
        _NOW,
        horizon_min=_HORIZON_MIN,
        window_min=_WINDOW_MIN,
        min_points=_MIN_POINTS,
        min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
    )
    assert forecast == pytest.approx(-3.0)


def test_clock_skew_kann_prognose_auf_none_degradieren():
    # Faellt das frischeste Reading durch Clock-Skew (G1 vorlaufend) in die Zukunft und
    # bleiben dadurch < min_points uebrig, degradiert die Prognose still auf None. Das ist
    # Fail-safe (None senkt die Risikostufe nie ab -> kein Under-Alarm), wird aber im
    # Scheduler-Kommentar (main.py) als bewusste Trenddegradierung dokumentiert.
    future = _reading(-1, 0.0)  # zukuenftig -> ausgeschlossen
    readings = [future, _reading(10, 1.0), _reading(0, 0.0)]  # nur 2 gueltige < min_points=3
    assert (
        forecast_surface_temp(
            readings,
            _NOW,
            horizon_min=_HORIZON_MIN,
            window_min=_WINDOW_MIN,
            min_points=_MIN_POINTS,
            min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
        )
        is None
    )


def test_leere_zeitreihe_keine_prognose():
    assert (
        forecast_surface_temp(
            [],
            _NOW,
            horizon_min=_HORIZON_MIN,
            window_min=_WINDOW_MIN,
            min_points=_MIN_POINTS,
            min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
        )
        is None
    )


def test_overflow_ergibt_keine_prognose():
    # Extrem grosse Werte lassen die Extrapolation nach +/-inf laufen -> Fail-safe None
    # (deckt den nicht-endlich-Guard am Ende von _project ab).
    huge = 1e308
    readings = [_reading(20, 0.0), _reading(10, huge / 2.0), _reading(0, huge)]
    assert (
        forecast_surface_temp(
            readings,
            _NOW,
            horizon_min=_HORIZON_MIN,
            window_min=_WINDOW_MIN,
            min_points=_MIN_POINTS,
            min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
        )
        is None
    )


def test_steile_rampe_wird_nach_unten_geclampt():
    # Blind-Spot-Nebenbefund: kuenstlich steile Rampe (z. B. Testdaten) extrapoliert
    # linear unter die physikalische Untergrenze. Der Clamp begrenzt auf
    # min_forecast_temp_c, ohne die GELB-Vorwarnung zu deaktivieren (fail-safe).
    # T_s faellt 10 °C/min: 0.0 -> -10.0 -> -20.0; Steigung -1.0/min -> in 30 min -50.0.
    readings = [_reading(20, 0.0), _reading(10, -10.0), _reading(0, -20.0)]
    forecast = forecast_surface_temp(
        readings,
        _NOW,
        horizon_min=_HORIZON_MIN,
        window_min=_WINDOW_MIN,
        min_points=_MIN_POINTS,
        min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
    )
    assert forecast is not None
    assert forecast == pytest.approx(_MIN_FORECAST_TEMP_C)


def test_clamp_greift_nicht_bei_physiologisch_normalem_trend():
    # Echter Sensorverlauf aendert sich langsam; der Clamp greift nicht.
    readings = [_reading(20, 2.0), _reading(10, 1.0), _reading(0, 0.0)]
    forecast = forecast_surface_temp(
        readings,
        _NOW,
        horizon_min=_HORIZON_MIN,
        window_min=_WINDOW_MIN,
        min_points=_MIN_POINTS,
        min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
    )
    assert forecast == pytest.approx(-3.0)


def test_defekte_untergrenze_liefert_keine_prognose():
    # NaN/inf als Clamp-Grenze ist eine defekte Konfiguration -> None (NF-01).
    readings = [_reading(20, 2.0), _reading(10, 1.0), _reading(0, 0.0)]
    assert (
        forecast_surface_temp(
            readings,
            _NOW,
            horizon_min=_HORIZON_MIN,
            window_min=_WINDOW_MIN,
            min_points=_MIN_POINTS,
            min_forecast_temp_c=float("nan"),
        )
        is None
    )


def test_naive_now_wirft():
    readings = [_reading(20, 2.0), _reading(10, 1.0), _reading(0, 0.0)]
    with pytest.raises(ValueError, match="zeitzonenbewusst"):
        forecast_surface_temp(
            readings,
            datetime(2026, 6, 27, 12, 0, 0),  # noqa: DTZ001 - bewusst naiv fuer den Test
            horizon_min=_HORIZON_MIN,
            window_min=_WINDOW_MIN,
            min_points=_MIN_POINTS,
            min_forecast_temp_c=_MIN_FORECAST_TEMP_C,
        )
