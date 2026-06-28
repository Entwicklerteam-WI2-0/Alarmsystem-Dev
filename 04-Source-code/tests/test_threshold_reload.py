"""Tests fuer `_load_active_thresholds` (DTB-63 Reload-Quelle in main.build_runtime).

Reload-Semantik: aktive Schwellen = zuletzt gespeicherter `threshold_set`; bei leerer
Tabelle, DB-Ausfall oder ungueltigem gespeichertem Satz fail-safe auf die JSON-Seed-
Config zurueckfallen (lieber die committete Basiskalibrierung als gar keine Schwellen).
"""

from dataclasses import asdict
from datetime import UTC, datetime

from src.config.loader import load_thresholds
from src.main import _load_active_thresholds
from src.model.enums import AuditEventType
from src.model.schemas import AuditLogEntry, ThresholdSet
from src.storage.repository import RepositoryError
from src.storage.threshold_set_repository import InMemoryThresholdSetRepository


def _audit() -> AuditLogEntry:
    return AuditLogEntry(
        ts=datetime(2026, 6, 28, tzinfo=UTC),
        event_type=AuditEventType.THRESHOLD_CHANGED,
        entity_type="threshold_set",
        actor="operator",
    )


def _store(repo: InMemoryThresholdSetRepository, params: dict) -> None:
    repo.append(
        ThresholdSet(
            name="satz",
            params=params,
            valid_from=datetime(2026, 6, 28, tzinfo=UTC),
            changed_by="operator",
        ),
        _audit(),
    )


def test_empty_db_falls_back_to_json_seed() -> None:
    # Leere Tabelle -> JSON-Seed (config/thresholds.json).
    assert _load_active_thresholds(InMemoryThresholdSetRepository()) == load_thresholds()


def test_latest_set_is_loaded_and_parsed() -> None:
    repo = InMemoryThresholdSetRepository()
    params = asdict(load_thresholds())
    params["betrieb"]["poll_interval_s"] = 20.0  # vom Default (30.0) abweichend
    _store(repo, params)
    result = _load_active_thresholds(repo)
    # Aktive Schwellen kommen aus dem gespeicherten Satz, nicht aus der JSON-Datei.
    assert result.betrieb.poll_interval_s == 20.0


def test_db_error_falls_back_to_json_seed() -> None:
    class _FailingRepo:
        def get_latest(self):
            raise RepositoryError("DB nicht erreichbar")

    assert _load_active_thresholds(_FailingRepo()) == load_thresholds()


def test_invalid_stored_set_falls_back_to_json_seed() -> None:
    # Gespeicherter Satz ist unvollstaendig/ungueltig -> ConfigError -> JSON-Seed (fail-safe).
    repo = InMemoryThresholdSetRepository()
    _store(repo, {"unvollstaendig": True})
    assert _load_active_thresholds(repo) == load_thresholds()
