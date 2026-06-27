"""Tests fuer die schreibenden /v1-Endpoints (DTB-63, NF-07)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.runtime import Runtime, get_runtime
from src.api.security import API_KEY_ENV
from src.config.loader import load_thresholds
from src.main import app
from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm
from src.storage.alarm_repository import InMemoryAlarmRepository

client = TestClient(app)

API_KEY = "testkey-12345"


def _active_alarm(alarm_id: int | None = None) -> Alarm:
    return Alarm(
        id=alarm_id,
        assessment_id=42,
        severity=AlarmSeverity.WARNING,
        raised_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
        state=AlarmState.ACTIVE,
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_ack_happy_path(monkeypatch, runtime: Runtime, alarm_repo: InMemoryAlarmRepository):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    alarm_id = alarm_repo.save(_active_alarm())
    app.dependency_overrides[get_runtime] = lambda: runtime

    resp = client.post(
        f"/v1/alarms/{alarm_id}/ack",
        headers={"X-API-Key": API_KEY},
        json={"operator": "tower-ops-01", "note": "Gesehen"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["alarm_id"] == alarm_id
    assert body["operator"] == "tower-ops-01"
    assert body["note"] == "Gesehen"
    assert "ts" in body
    assert resp.headers["cache-control"] == "no-store"


def test_ack_without_key_returns_401(monkeypatch, runtime: Runtime):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    app.dependency_overrides[get_runtime] = lambda: runtime

    resp = client.post("/v1/alarms/1/ack", json={"operator": "tower-ops-01"})

    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "UNAUTHORIZED"
    assert "detail" not in body
    assert resp.headers["cache-control"] == "no-store"


def test_ack_with_wrong_key_returns_401(monkeypatch, runtime: Runtime):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    app.dependency_overrides[get_runtime] = lambda: runtime

    resp = client.post(
        "/v1/alarms/1/ack",
        headers={"X-API-Key": "falsch"},
        json={"operator": "tower-ops-01"},
    )

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_ack_unconfigured_server_returns_503(monkeypatch, runtime: Runtime):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    app.dependency_overrides[get_runtime] = lambda: runtime

    resp = client.post(
        "/v1/alarms/1/ack",
        headers={"X-API-Key": "egal"},
        json={"operator": "tower-ops-01"},
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


def test_ack_unknown_alarm_returns_404(monkeypatch, runtime: Runtime):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    app.dependency_overrides[get_runtime] = lambda: runtime

    resp = client.post(
        "/v1/alarms/99/ack",
        headers={"X-API-Key": API_KEY},
        json={"operator": "tower-ops-01"},
    )

    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert "99" in body["message"]


def test_ack_double_ack_returns_409(
    monkeypatch, runtime: Runtime, alarm_repo: InMemoryAlarmRepository
):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    alarm_id = alarm_repo.save(_active_alarm())
    app.dependency_overrides[get_runtime] = lambda: runtime

    client.post(
        f"/v1/alarms/{alarm_id}/ack",
        headers={"X-API-Key": API_KEY},
        json={"operator": "tower-ops-01"},
    )
    resp = client.post(
        f"/v1/alarms/{alarm_id}/ack",
        headers={"X-API-Key": API_KEY},
        json={"operator": "tower-ops-01"},
    )

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "ALARM_ALREADY_ACKNOWLEDGED"
    assert "acknowledged" in body["message"]


def test_ack_invalid_path_id_returns_validation_error(monkeypatch, runtime: Runtime):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    app.dependency_overrides[get_runtime] = lambda: runtime

    resp = client.post(
        "/v1/alarms/0/ack",
        headers={"X-API-Key": API_KEY},
        json={"operator": "tower-ops-01"},
    )

    assert resp.status_code == 422


def test_config_update_happy_path(monkeypatch, tmp_path, runtime: Runtime):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    fake_path = tmp_path / "thresholds.json"
    monkeypatch.setattr("src.config.loader.DEFAULT_CONFIG_PATH", fake_path)
    app.dependency_overrides[get_runtime] = lambda: runtime

    # Runtime-Attribut vor dem Request sichern, damit andere Tests (z. B.
    # test_current_runtime_not_initialized_returns_503) nicht durcheinander kommen.
    _missing = object()
    previous_runtime = getattr(app.state, "runtime", _missing)

    def _reload_runtime():
        return SimpleNamespace(thresholds=load_thresholds())

    with patch("src.main.build_runtime", side_effect=_reload_runtime):
        resp = client.post(
            "/v1/config",
            headers={"X-API-Key": API_KEY},
            json={
                "vereisung": {
                    "t_s_gefrierpunkt_c": -1.0,
                    "t_s_gelb_auffang_c": 2.0,
                    "delta_t_kondensation_k": 0.0,
                    "delta_t_feucht_k": 1.5,
                },
                "prognose": {"t_s_grenz_c": 0.0},
                "hysterese": {
                    "on_delay_s": 60.0,
                    "max_continuity_gap_s": 150.0,
                    "downgrade_stable_s": 300.0,
                    "downgrade_undershoot_c": 0.5,
                },
                "datenqualitaet": {
                    "stale_timeout_s": 120.0,
                    "max_temp_jump_c_per_min": 5.0,
                    "flatline_timeout_min": 15.0,
                    "flatline_epsilon_c": 0.01,
                    "max_clock_skew_s": 5.0,
                    "min_plausible_dew_point_c": -50.0,
                },
                "plausibilitaet": {
                    "min_temp_c": -50.0,
                    "max_temp_c": 50.0,
                    "min_humidity_pct": 0.0,
                    "max_humidity_pct": 100.0,
                    "min_pressure_hpa": 800.0,
                    "max_pressure_hpa": 1100.0,
                },
                "betrieb": {"poll_interval_s": 30.0},
            },
        )

    if previous_runtime is _missing:
        delattr(app.state, "runtime")
    else:
        app.state.runtime = previous_runtime

    assert resp.status_code == 200
    body = resp.json()
    assert body["vereisung"]["t_s_gefrierpunkt_c"] == -1.0
    assert fake_path.exists()


def test_config_update_without_key_returns_401(monkeypatch, runtime: Runtime):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    app.dependency_overrides[get_runtime] = lambda: runtime

    resp = client.post("/v1/config", json={"vereisung": {"t_s_gefrierpunkt_c": -1.0}})

    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_config_update_invalid_thresholds_returns_422(monkeypatch, runtime: Runtime):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    app.dependency_overrides[get_runtime] = lambda: runtime

    resp = client.post(
        "/v1/config",
        headers={"X-API-Key": API_KEY},
        json={
            "vereisung": {
                "t_s_gefrierpunkt_c": -1.0,
                "t_s_gelb_auffang_c": 2.0,
                "delta_t_kondensation_k": 0.0,
                "delta_t_feucht_k": 1.5,
            },
            "prognose": {"t_s_grenz_c": 0.0},
            "hysterese": {
                "on_delay_s": 60.0,
                "max_continuity_gap_s": 150.0,
                "downgrade_stable_s": 300.0,
                "downgrade_undershoot_c": 0.5,
            },
            "datenqualitaet": {
                "stale_timeout_s": 120.0,
                "max_temp_jump_c_per_min": 5.0,
                "flatline_timeout_min": 15.0,
                "flatline_epsilon_c": 0.01,
                "max_clock_skew_s": 5.0,
                "min_plausible_dew_point_c": -50.0,
            },
            "plausibilitaet": {
                "min_temp_c": -50.0,
                "max_temp_c": 50.0,
                "min_humidity_pct": 0.0,
                "max_humidity_pct": 100.0,
                "min_pressure_hpa": 800.0,
                "max_pressure_hpa": 1100.0,
            },
            "betrieb": {"poll_interval_s": -5.0},
        },
    )

    assert resp.status_code == 422
