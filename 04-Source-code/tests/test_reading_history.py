"""Unit-Tests fuer die Historie-Abfrage `get_readings` (DTB-34, FA-03).

DB-frei: prueft die `InMemoryReadingRepository`-Implementierung, die exakt die
Semantik der PyMySQL-`ReadingRepository` spiegelt (Filter `sensor_id`/`from`/`to`,
Sortierung `order`, `limit` behaelt die FRISCHESTEN). Die Integrations-Variante gegen
eine echte MariaDB steht in `test_storage_repository.py` (skippt ohne DB).
"""

from datetime import UTC, datetime

import pytest

from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.repository import InMemoryReadingRepository


def _reading(sensor_id: str, minute: int, temp: float) -> Reading:
    ts = datetime(2026, 6, 23, 10, minute, 0, tzinfo=UTC)
    return Reading(
        sensor_id=sensor_id,
        measured_at=ts,
        received_at=ts,
        surface_temp_c=temp,
        air_temp_c=1.0,
        humidity_pct=80.0,
        source=Source.REAL,
        status=SensorStatus.OK,
    )


@pytest.fixture
def seeded_repo() -> InMemoryReadingRepository:
    repo = InMemoryReadingRepository()
    # minute 0..3 fuer denselben Sensor, aufsteigende Temperatur = aufsteigende Zeit
    for minute in range(4):
        repo.save(_reading("anr-rwy-01", minute, float(minute)))
    return repo


def test_get_readings_default_desc_newest_first(seeded_repo: InMemoryReadingRepository) -> None:
    result = seeded_repo.get_readings()
    assert [r.surface_temp_c for r in result] == [3.0, 2.0, 1.0, 0.0]


def test_get_readings_order_asc_oldest_first(seeded_repo: InMemoryReadingRepository) -> None:
    result = seeded_repo.get_readings(order="asc")
    assert [r.surface_temp_c for r in result] == [0.0, 1.0, 2.0, 3.0]


def test_get_readings_filters_by_sensor_id() -> None:
    repo = InMemoryReadingRepository()
    repo.save(_reading("anr-a", 0, 1.0))
    repo.save(_reading("anr-b", 1, 2.0))
    result = repo.get_readings(sensor_id="anr-a")
    assert len(result) == 1
    assert result[0].sensor_id == "anr-a"


def test_get_readings_without_sensor_id_spans_all_sensors() -> None:
    repo = InMemoryReadingRepository()
    repo.save(_reading("anr-a", 0, 1.0))
    repo.save(_reading("anr-b", 1, 2.0))
    result = repo.get_readings()
    assert {r.sensor_id for r in result} == {"anr-a", "anr-b"}


def test_get_readings_from_to_bounds_inclusive(seeded_repo: InMemoryReadingRepository) -> None:
    start = datetime(2026, 6, 23, 10, 1, 0, tzinfo=UTC)
    end = datetime(2026, 6, 23, 10, 2, 0, tzinfo=UTC)
    result = seeded_repo.get_readings(start=start, end=end, order="asc")
    # Beide Grenzen inklusiv -> Minute 1 und 2.
    assert [r.surface_temp_c for r in result] == [1.0, 2.0]


def test_get_readings_only_from_bound(seeded_repo: InMemoryReadingRepository) -> None:
    start = datetime(2026, 6, 23, 10, 2, 0, tzinfo=UTC)
    result = seeded_repo.get_readings(start=start, order="asc")
    assert [r.surface_temp_c for r in result] == [2.0, 3.0]


def test_get_readings_only_to_bound(seeded_repo: InMemoryReadingRepository) -> None:
    end = datetime(2026, 6, 23, 10, 1, 0, tzinfo=UTC)
    result = seeded_repo.get_readings(end=end, order="asc")
    assert [r.surface_temp_c for r in result] == [0.0, 1.0]


def test_get_readings_limit_keeps_freshest_then_orders(
    seeded_repo: InMemoryReadingRepository,
) -> None:
    # limit kappt am AELTEREN Ende (openapi.yaml: "am jeweils aelteren Ende abgeschnitten")
    # -> die FRISCHESTEN 2 behalten, dann in der gewuenschten Reihenfolge ausgeben.
    desc = seeded_repo.get_readings(limit=2, order="desc")
    assert [r.surface_temp_c for r in desc] == [3.0, 2.0]
    asc = seeded_repo.get_readings(limit=2, order="asc")
    assert [r.surface_temp_c for r in asc] == [2.0, 3.0]


def test_get_readings_empty_repo_returns_empty_tuple() -> None:
    assert InMemoryReadingRepository().get_readings() == ()


def test_get_readings_rejects_invalid_order(seeded_repo: InMemoryReadingRepository) -> None:
    with pytest.raises(ValueError, match="order"):
        seeded_repo.get_readings(order="sideways")


@pytest.mark.parametrize("bad_limit", [0, -1, -100])
def test_get_readings_rejects_non_positive_limit(
    seeded_repo: InMemoryReadingRepository, bad_limit: int
) -> None:
    with pytest.raises(ValueError, match="limit muss positiv sein"):
        seeded_repo.get_readings(limit=bad_limit)


def test_get_readings_rejects_naive_from(seeded_repo: InMemoryReadingRepository) -> None:
    with pytest.raises(ValueError, match="zeitzonenbewusst"):
        seeded_repo.get_readings(start=datetime(2026, 6, 23, 10, 0, 0))


def test_get_readings_rejects_naive_to(seeded_repo: InMemoryReadingRepository) -> None:
    with pytest.raises(ValueError, match="zeitzonenbewusst"):
        seeded_repo.get_readings(end=datetime(2026, 6, 23, 10, 0, 0))
