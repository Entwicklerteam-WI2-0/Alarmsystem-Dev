"""Tests fuer GET /v1/alarms (DTB-31, Resync/Zustands-Abfrage).

Prueft: der Endpoint liefert offene Alarme aus dem AlarmRepository als Resync-Backstop
(E-37, kein Entdeckungs-Poll), filtert optional auf einen Alarm-Zustand, validiert den
state-Filter (400 im Contract-Format), reicht limit durch und bleibt bei
Persistenzfehlern/Nicht-Verfuegbarkeit fail-safe (503 im Contract-Format `Error{code,message}`).

Reiner Lesepfad (RB-01-neutral): kein Zustandswechsel, kein Aktor.
"""

from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.exceptions import RuntimeNotReadyError
from src.api.responses import NO_STORE_HEADERS, SERVICE_UNAVAILABLE_CODE
from src.api.runtime import get_runtime
from src.main import app
from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm
from src.storage.repository import RepositoryError

client = TestClient(app)

UTC_NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def _alarm(
    id_: int = 1,
    *,
    severity: AlarmSeverity = AlarmSeverity.WARNING,
    state: AlarmState = AlarmState.ACTIVE,
    raised_at: datetime = UTC_NOW,
) -> Alarm:
    return Alarm(
        id=id_,
        assessment_id=1,
        severity=severity,
        raised_at=raised_at,
        state=state,
    )


class _FakeAlarmRepo:
    """Erfasst die get_alarms-Aufrufe und liefert vorgegebene Alarme bzw. wirft einen Fehler."""

    def __init__(self, alarms: list[Alarm] | None = None, error: Exception | None = None) -> None:
        self._alarms = alarms if alarms is not None else []
        self._error = error
        self.calls: list[tuple[AlarmState | None, int]] = []

    def get_alarms(self, state: AlarmState | None = None, limit: int = 100) -> list[Alarm]:
        self.calls.append((state, limit))
        if self._error is not None:
            raise self._error
        return list(self._alarms)


def _override_runtime(repo: _FakeAlarmRepo) -> None:
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(alarm_repo=repo)


def _assert_no_store_header(resp: object) -> None:
    key, value = next(iter(NO_STORE_HEADERS.items()))
    assert resp.headers[key.lower()] == value


def test_list_alarms_returns_open_by_default() -> None:
    repo = _FakeAlarmRepo([_alarm(1), _alarm(2, severity=AlarmSeverity.CRITICAL)])
    _override_runtime(repo)

    resp = client.get("/v1/alarms")

    assert resp.status_code == 200
    body = resp.json()
    assert [a["id"] for a in body] == [1, 2]
    # Ohne state-Filter fragt der Endpoint den Repo-Default (offene Alarme) ab.
    assert repo.calls == [(None, 100)]
    _assert_no_store_header(resp)


def test_list_alarms_response_shape_matches_contract() -> None:
    repo = _FakeAlarmRepo([_alarm(7, severity=AlarmSeverity.CRITICAL)])
    _override_runtime(repo)

    item = client.get("/v1/alarms").json()[0]

    # Wire-Form exakt nach openapi.yaml-Schema `Alarm` (required: id..state); raised_at
    # als UTC ISO-8601 mit Z-Suffix (Contract §2a).
    assert item == {
        "id": 7,
        "assessment_id": 1,
        "severity": "critical",
        "raised_at": "2026-06-28T12:00:00Z",
        "state": "active",
    }


def test_list_alarms_empty_returns_empty_list() -> None:
    repo = _FakeAlarmRepo([])
    _override_runtime(repo)

    resp = client.get("/v1/alarms")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.parametrize(
    "state_value, expected",
    [
        ("active", AlarmState.ACTIVE),
        ("acknowledged", AlarmState.ACKNOWLEDGED),
        ("cleared", AlarmState.CLEARED),
    ],
)
def test_list_alarms_state_filter_is_passed_through(state_value: str, expected: AlarmState) -> None:
    repo = _FakeAlarmRepo([])
    _override_runtime(repo)

    resp = client.get(f"/v1/alarms?state={state_value}")

    assert resp.status_code == 200
    assert repo.calls == [(expected, 100)]


def test_list_alarms_invalid_state_returns_400_without_touching_repo() -> None:
    repo = _FakeAlarmRepo([_alarm(1)])
    _override_runtime(repo)

    resp = client.get("/v1/alarms?state=bogus")

    # Contract (openapi.yaml): ungueltiger state-Filter -> 400 im Error-Format.
    assert resp.status_code == 400
    body = resp.json()
    assert set(body) == {"code", "message"}  # {code, message}, nie FastAPIs {detail}
    # Validierung VOR dem Repo: ein ungueltiger Filter loest keinen DB-Zugriff aus.
    assert repo.calls == []


def test_list_alarms_limit_is_passed_through() -> None:
    repo = _FakeAlarmRepo([])
    _override_runtime(repo)

    resp = client.get("/v1/alarms?limit=5")

    assert resp.status_code == 200
    assert repo.calls == [(None, 5)]


@pytest.mark.parametrize("bad_limit", [0, 501, -1])
def test_list_alarms_limit_out_of_range_rejected(bad_limit: int) -> None:
    repo = _FakeAlarmRepo([])
    _override_runtime(repo)

    resp = client.get(f"/v1/alarms?limit={bad_limit}")

    # Query-Bounds (1..500) verletzt -> globaler RequestValidationError-Handler: 400
    # Error{code,message} (Contract D: Query-Fehler = 400, nicht 422). Kein DB-Zugriff.
    assert resp.status_code == 400
    assert set(resp.json()) == {"code", "message"}
    assert repo.calls == []


def test_list_alarms_repository_error_is_failsafe_503() -> None:
    repo = _FakeAlarmRepo(error=RepositoryError("DB weg"))
    _override_runtime(repo)

    resp = client.get("/v1/alarms")

    # NF-01: DB-Ausfall -> 503 im Contract-Format, nie ein roher 500/{detail}.
    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == SERVICE_UNAVAILABLE_CODE
    _assert_no_store_header(resp)


def test_list_alarms_wire_mapping_drift_is_failsafe_503() -> None:
    # Repo liefert einen Alarm OHNE id (DB-/Mapping-Drift) -> AlarmResponse erzwingt id:int,
    # die Validierung schlaegt fehl -> fail-safe 503 (NF-01), nie ein roher 500.
    drift = Alarm(assessment_id=1, severity=AlarmSeverity.WARNING, raised_at=UTC_NOW)  # id=None
    repo = _FakeAlarmRepo([drift])
    _override_runtime(repo)

    resp = client.get("/v1/alarms")

    assert resp.status_code == 503
    assert resp.json()["code"] == SERVICE_UNAVAILABLE_CODE


def test_list_alarms_unexpected_error_is_failsafe_503() -> None:
    repo = _FakeAlarmRepo(error=RuntimeError("unerwartet"))
    _override_runtime(repo)

    resp = client.get("/v1/alarms")

    # Letzter Fail-safe: JEDER Fehlerpfad liefert Error{code,message} (NF-01), nie 500.
    assert resp.status_code == 503
    assert resp.json()["code"] == SERVICE_UNAVAILABLE_CODE


def test_list_alarms_runtime_not_ready_is_503() -> None:
    def _not_ready() -> None:
        raise RuntimeNotReadyError("Runtime nicht initialisiert.")

    app.dependency_overrides[get_runtime] = _not_ready

    resp = client.get("/v1/alarms")

    assert resp.status_code == 503
    assert set(resp.json()) == {"code", "message"}
