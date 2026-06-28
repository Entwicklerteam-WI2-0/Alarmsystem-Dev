"""Tests fuer die Forecast-Bruecke (DTB-33): Zeitreihe lesen -> reinen Producer rufen.

Die Bruecke verbindet Repository (DB) und reine Trend-Funktion. Fail-safe (NF-01):
kein Reading oder ein Repository-Fehler liefert None ("keine Prognose"), nie ein Crash.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from src.config.loader import PrognoseSchwellen, load_thresholds
from src.forecast.bridge import compute_forecast_for_cycle
from src.model.schemas import Reading
from src.storage.repository import Repository, RepositoryError


@pytest.fixture
def prognose() -> PrognoseSchwellen:
    return load_thresholds().prognose


_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)


class _FakeReadingRepo(Repository):
    """Minimaler Repo-Stub mit get_since; merkt sich die Aufrufe."""

    def __init__(self, readings: Sequence[Reading], *, raises: bool = False) -> None:
        self._readings = readings
        self._raises = raises
        self.calls: list[tuple[str, datetime, int]] = []

    def save(self, reading: Reading) -> int:
        raise NotImplementedError

    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        raise NotImplementedError

    def get_since(self, sensor_id: str, since: datetime, limit: int = 1000) -> Sequence[Reading]:
        self.calls.append((sensor_id, since, limit))
        if self._raises:
            raise RepositoryError("boom")
        return self._readings

    def get_readings(self, **_kwargs: object) -> Sequence[Reading]:
        raise NotImplementedError  # Bridge nutzt nur get_since (DTB-34 Serving)


def _reading(minutes_ago: float, surface: float) -> Reading:
    ts = _NOW - timedelta(minutes=minutes_ago)
    return Reading(
        sensor_id="anr-rwy-01",
        measured_at=ts,
        surface_temp_c=surface,
        air_temp_c=surface + 1.0,
        humidity_pct=80.0,
        received_at=ts,
    )


def test_kein_reading_keine_prognose_und_kein_db_zugriff(prognose):
    repo = _FakeReadingRepo([])
    assert compute_forecast_for_cycle(None, repo, prognose, _NOW) is None
    assert repo.calls == []  # ohne Reading kein DB-Zugriff


def test_fallender_trend_liefert_prognose_und_liest_richtiges_fenster(prognose):
    series = [_reading(20, 2.0), _reading(10, 1.0), _reading(0, 0.0)]
    repo = _FakeReadingRepo(series)

    forecast = compute_forecast_for_cycle(series[-1], repo, prognose, _NOW)

    assert forecast == pytest.approx(-3.0)
    sensor_id, since, limit = repo.calls[0]
    assert sensor_id == "anr-rwy-01"
    assert since == _NOW - timedelta(minutes=prognose.trend_window_min)
    assert limit == prognose.max_readings_limit


def test_repository_fehler_ist_failsafe_none(prognose):
    repo = _FakeReadingRepo([], raises=True)
    assert compute_forecast_for_cycle(_reading(0, 0.0), repo, prognose, _NOW) is None


def test_leere_zeitreihe_ist_failsafe_none(prognose):
    # Reading vorhanden, aber noch keine Historie -> DB wird abgefragt, liefert None.
    repo = _FakeReadingRepo([])
    result = compute_forecast_for_cycle(_reading(0, 1.0), repo, prognose, _NOW)
    assert result is None
    assert len(repo.calls) == 1  # DB wurde abgefragt (kein Kurzschluss)


def test_naives_now_propagiert_valueerror_statt_failsafe_none(prognose):
    # bridge.py (Docstring + Inline-Kommentar) haelt fest: ein naives `now` ist ein
    # Programmierfehler, kein transienter Datenlayer-Fehler. Der ValueError-Guard aus
    # trend.py wird daher bewusst NICHT als "keine Prognose" (None) maskiert, sondern
    # propagiert sichtbar -- nur RepositoryError ist fail-safe. Regressions-Guard fuer
    # genau diese Intention (sonst koennte ein spaeteres try/except den Fehler still
    # verschlucken und die Vorwarnung waere unbemerkt tot).
    # Hinweis: Der Scheduler in main.py fängt diesen (und alle anderen unerwarteten
    # Fehler) in seinem except Exception-Block ab, loggt ihn und setzt forecast=None,
    # damit die Bewertung unbedingt weiterläuft (NF-01).
    series = [_reading(20, 2.0), _reading(10, 1.0), _reading(0, 0.0)]
    repo = _FakeReadingRepo(series)
    naive_now = _NOW.replace(tzinfo=None)

    with pytest.raises(ValueError, match="zeitzonenbewusst"):
        compute_forecast_for_cycle(series[-1], repo, prognose, naive_now)
