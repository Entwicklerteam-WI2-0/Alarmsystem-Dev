"""Tests fuer POST /v1/alarms/{id}/ack (DTB-24, FA-10, G2->G3-Contract).

Belegt den Quittierungs-Endpoint gegen den **eingefrorenen Contract** (openapi.yaml):
Erfolg 200 + Acknowledgement, sowie alle Fehlerbilder im Contract-Fehlerformat
`Error {code, message}` (nie FastAPIs `{detail}`):

- `id < 1`           -> 400 BAD_REQUEST
- Body ungueltig     -> 422 UNPROCESSABLE_ENTITY (globaler RequestValidationError-Handler)
- Alarm fehlt        -> 404 NOT_FOUND
- bereits quittiert  -> 409 ALARM_ALREADY_ACKNOWLEDGED (Double-Ack, NF-09, nicht idempotent)
- Persistenz-Ausfall -> 503 SERVICE_UNAVAILABLE

Auth: im Prototyp (M2/Contract) bewusst KEIN Auth-Header (additiv in M3, DTB-63).
Das ack_repo wird ueber die get_runtime-Dependency injiziert (app.dependency_overrides),
ohne DB und ohne Lifespan/Scheduler.
"""

from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app, get_runtime
from src.model.enums import AlarmState
from src.storage.acknowledgement_repository import InMemoryAcknowledgementRepository
from src.storage.repository import RepositoryError

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Jeder Test setzt seine eigene Runtime; danach aufraeumen."""
    yield
    app.dependency_overrides.clear()


def _override_ack_repo(ack_repo: object) -> None:
    # Der Endpoint liest ausschliesslich runtime.ack_repo -> ein SimpleNamespace genuegt
    # (kein vollstaendiger Runtime-Graph noetig).
    runtime = SimpleNamespace(ack_repo=ack_repo)
    app.dependency_overrides[get_runtime] = lambda: runtime


class _FailingAckRepo:
    """Quittierungs-Repo, das einen Persistenz-Ausfall simuliert (-> 503)."""

    def acknowledge(self, *_args: object, **_kwargs: object) -> object:
        raise RepositoryError("ack-DB nicht erreichbar")


def _assert_error_envelope(response: httpx.Response, status: int, code: str) -> None:
    """Fehlerantwort MUSS exakt das Contract-Format `{code, message}` tragen (nie `{detail}`)."""
    assert response.status_code == status
    # POST-Fehler tragen ebenfalls no-store (Konvention der /v1-Naht).
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body.keys()) == {"code", "message"}
    assert body["code"] == code
    assert isinstance(body["message"], str) and body["message"]


# ---------------------------------------------------------------------------
# 200 — Quittierung gespeichert (Gutfall)
# ---------------------------------------------------------------------------


def test_ack_happy_path_returns_200_and_persists():
    ack_repo = InMemoryAcknowledgementRepository({1: AlarmState.ACTIVE})
    _override_ack_repo(ack_repo)

    response = client.post(
        "/v1/alarms/1/ack",
        json={"operator": "tower-ops-01", "note": "Sichtkontrolle"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["alarm_id"] == 1
    assert body["operator"] == "tower-ops-01"
    assert body["note"] == "Sichtkontrolle"
    assert body["id"] == 1
    assert body["ts"] is not None
    # Seiteneffekt: State active -> acknowledged, ein Audit-Eintrag (NF-09).
    assert ack_repo.state_of(1) is AlarmState.ACKNOWLEDGED
    assert len(ack_repo.acknowledgements) == 1
    assert len(ack_repo.audit_entries) == 1
    # ts ist ein gueltiger ISO-8601-Zeitstempel.
    datetime.fromisoformat(body["ts"])


def test_ack_without_note_returns_200():
    ack_repo = InMemoryAcknowledgementRepository({5: AlarmState.ACTIVE})
    _override_ack_repo(ack_repo)

    response = client.post("/v1/alarms/5/ack", json={"operator": "tower-ops-02"})

    assert response.status_code == 200
    assert response.json()["note"] is None


# ---------------------------------------------------------------------------
# Fehlerbilder (Contract-Fehlerformat Error{code,message})
# ---------------------------------------------------------------------------


def test_ack_invalid_id_returns_400():
    # id=0 verletzt die Geschaeftsregel (minimum 1) -> 400, NICHT 422 (Param ohne ge-Constraint).
    _override_ack_repo(InMemoryAcknowledgementRepository({1: AlarmState.ACTIVE}))

    response = client.post("/v1/alarms/0/ack", json={"operator": "tower-ops-01"})

    _assert_error_envelope(response, 400, "BAD_REQUEST")


def test_ack_unknown_alarm_returns_404():
    _override_ack_repo(InMemoryAcknowledgementRepository())  # kein Alarm geseedet

    response = client.post("/v1/alarms/99/ack", json={"operator": "tower-ops-01"})

    _assert_error_envelope(response, 404, "NOT_FOUND")


def test_ack_already_acknowledged_returns_409():
    _override_ack_repo(InMemoryAcknowledgementRepository({1: AlarmState.ACKNOWLEDGED}))

    response = client.post("/v1/alarms/1/ack", json={"operator": "tower-ops-01"})

    _assert_error_envelope(response, 409, "ALARM_ALREADY_ACKNOWLEDGED")


def test_ack_double_ack_second_call_returns_409():
    _override_ack_repo(InMemoryAcknowledgementRepository({1: AlarmState.ACTIVE}))

    first = client.post("/v1/alarms/1/ack", json={"operator": "tower-ops-01"})
    second = client.post("/v1/alarms/1/ack", json={"operator": "tower-ops-09"})

    assert first.status_code == 200
    # NF-09: erneute Quittierung wird abgelehnt (nicht idempotent, kein stilles Schlucken).
    _assert_error_envelope(second, 409, "ALARM_ALREADY_ACKNOWLEDGED")


def test_ack_missing_operator_returns_422():
    # Body ohne Pflichtfeld operator -> 422 im Contract-Format (NICHT FastAPIs {detail}).
    _override_ack_repo(InMemoryAcknowledgementRepository({1: AlarmState.ACTIVE}))

    response = client.post("/v1/alarms/1/ack", json={"note": "ohne operator"})

    _assert_error_envelope(response, 422, "UNPROCESSABLE_ENTITY")


def test_ack_empty_operator_returns_422():
    # operator = "" verletzt min_length=1 -> 422.
    _override_ack_repo(InMemoryAcknowledgementRepository({1: AlarmState.ACTIVE}))

    response = client.post("/v1/alarms/1/ack", json={"operator": ""})

    _assert_error_envelope(response, 422, "UNPROCESSABLE_ENTITY")


def test_ack_repository_failure_returns_503():
    _override_ack_repo(_FailingAckRepo())

    response = client.post("/v1/alarms/1/ack", json={"operator": "tower-ops-01"})

    _assert_error_envelope(response, 503, "SERVICE_UNAVAILABLE")


def test_ack_runtime_not_initialized_returns_503():
    # Kein dependency_override + keine Lifespan -> app.state.runtime fehlt. get_runtime-Guard +
    # Exception-Handler muessen das contract-konform als 503 melden, nie als rohes 500/{detail}.
    response = client.post("/v1/alarms/1/ack", json={"operator": "tower-ops-01"})

    _assert_error_envelope(response, 503, "SERVICE_UNAVAILABLE")
