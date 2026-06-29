"""Tests fuer GET /v1/audit (DB-Spiegel / Live-Ereignis-Log, read-only, NF-09).

Prueft: der Endpoint liefert die neuesten Audit-Eintraege (neueste zuerst) aus dem
AuditRepository, respektiert `limit`, bleibt fail-safe bei Persistenzfehlern (503 im
Contract-Format Error{code,message}) und das InMemory-`get_recent` verhaelt sich
erwartet. Reiner Lese-Pfad -- der append-only Write-Pfad bleibt unveraendert.
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.exceptions import RuntimeNotReadyError
from src.api.responses import NO_STORE_HEADERS
from src.api.runtime import get_runtime
from src.main import app
from src.model.enums import AuditEventType
from src.model.schemas import AuditLogEntry, AuditLogResponse
from src.storage.audit_repository import InMemoryAuditRepository
from src.storage.repository import RepositoryError

client = TestClient(app)

_NOW = datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def audit_repo() -> InMemoryAuditRepository:
    return InMemoryAuditRepository()


def _entry(event_type: AuditEventType, offset_s: int = 0, actor: str = "system") -> AuditLogEntry:
    return AuditLogEntry(
        ts=_NOW + timedelta(seconds=offset_s),
        event_type=event_type,
        entity_type="assessment",
        entity_id=1,
        actor=actor,
        detail={"risk_level": "red"},
    )


# --- InMemory get_recent (read-only) ---


def test_inmemory_get_recent_newest_first() -> None:
    repo = InMemoryAuditRepository()
    repo.append(_entry(AuditEventType.READING_INGESTED, 0))
    repo.append(_entry(AuditEventType.ASSESSMENT_MADE, 10))
    repo.append(_entry(AuditEventType.ALARM_RAISED, 20))
    recent = repo.get_recent()
    assert [e.event_type for e in recent] == [
        AuditEventType.ALARM_RAISED,
        AuditEventType.ASSESSMENT_MADE,
        AuditEventType.READING_INGESTED,
    ]


def test_inmemory_get_recent_respects_limit() -> None:
    repo = InMemoryAuditRepository()
    for i in range(5):
        repo.append(_entry(AuditEventType.ASSESSMENT_MADE, i))
    assert len(repo.get_recent(limit=2)) == 2


def test_inmemory_get_recent_invalid_limit_raises() -> None:
    with pytest.raises(ValueError):
        InMemoryAuditRepository().get_recent(limit=0)


# --- Endpoint GET /v1/audit ---


def test_get_audit_returns_entries_newest_first(audit_repo: InMemoryAuditRepository) -> None:
    audit_repo.append(_entry(AuditEventType.ASSESSMENT_MADE, 0))
    audit_repo.append(_entry(AuditEventType.ALARM_RAISED, 10))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(audit_repo=audit_repo)

    resp = client.get("/v1/audit")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["event_type"] == "alarm_raised"
    assert body[1]["event_type"] == "assessment_made"
    for key, value in NO_STORE_HEADERS.items():
        assert resp.headers[key.lower()] == value


def test_get_audit_empty_returns_200_empty_list(audit_repo: InMemoryAuditRepository) -> None:
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(audit_repo=audit_repo)
    resp = client.get("/v1/audit")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_audit_respects_limit(audit_repo: InMemoryAuditRepository) -> None:
    for i in range(5):
        audit_repo.append(_entry(AuditEventType.ASSESSMENT_MADE, i))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(audit_repo=audit_repo)
    resp = client.get("/v1/audit", params={"limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_audit_limit_out_of_range_returns_400(audit_repo: InMemoryAuditRepository) -> None:
    # limit=0 verletzt ge=1 -> globaler RequestValidationError-Handler -> 400 (Query-Fehler).
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(audit_repo=audit_repo)
    resp = client.get("/v1/audit", params={"limit": 0})
    assert resp.status_code == 400
    assert resp.json()["code"] == "BAD_REQUEST"
    assert "detail" not in resp.json()


def test_get_audit_repository_error_returns_503(audit_repo: InMemoryAuditRepository) -> None:
    def _failing(*args: object, **kwargs: object) -> object:
        raise RepositoryError("DB nicht erreichbar")

    audit_repo.get_recent = _failing  # type: ignore[method-assign]
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(audit_repo=audit_repo)
    resp = client.get("/v1/audit")
    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"
    assert "detail" not in resp.json()


def test_get_audit_runtime_not_ready_returns_503() -> None:
    def _not_ready() -> object:
        raise RuntimeNotReadyError("test: runtime fehlt")

    app.dependency_overrides[get_runtime] = _not_ready
    resp = client.get("/v1/audit")
    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


def test_get_audit_response_matches_schema(audit_repo: InMemoryAuditRepository) -> None:
    audit_repo.append(_entry(AuditEventType.ALARM_ACKNOWLEDGED, 0, actor="lucas"))
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(audit_repo=audit_repo)
    resp = client.get("/v1/audit")
    assert resp.status_code == 200
    parsed = AuditLogResponse.model_validate(resp.json()[0])
    assert parsed.id is not None
    assert parsed.actor == "lucas"
    assert parsed.detail == {"risk_level": "red"}
