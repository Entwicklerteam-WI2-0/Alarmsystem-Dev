"""Tests fuer PUT /v1/thresholds (DTB-63, NF-07): Auth + versioniertes Schreiben + Audit.

Prueft die schreibende Naht gegen den Contract: 401/422/503 im Format
`Error {code, message}` (nie `{detail}`), versioniertes Persistieren + verknuepfter
`threshold_changed`-Audit-Eintrag (NF-09), und als Regression (#116) der non-ASCII-401.
Reload-Semantik (Wirksamkeit erst beim Neustart) wird in test_threshold_reload.py
auf der Lade-Seite geprueft.
"""

from dataclasses import asdict
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.runtime import get_runtime
from src.api.security import API_KEY_ENV
from src.config.loader import load_thresholds
from src.main import app
from src.model.enums import AuditEventType
from src.storage.repository import RepositoryError
from src.storage.threshold_set_repository import InMemoryThresholdSetRepository

client = TestClient(app)
_KEY = "geheim-test-key-123"
_AUTH = {"Authorization": f"Bearer {_KEY}"}


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _valid_body(**overrides) -> dict:
    body = {"changed_by": "operator-anr", "thresholds": asdict(load_thresholds())}
    body.update(overrides)
    return body


def _override_runtime() -> InMemoryThresholdSetRepository:
    repo = InMemoryThresholdSetRepository()
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(threshold_set_repo=repo)
    return repo


def test_put_without_auth_returns_401_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    _override_runtime()
    resp = client.put("/v1/thresholds", json=_valid_body())
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "UNAUTHORIZED"
    assert "detail" not in body  # FastAPI-Default {detail} wuerde die Naht brechen
    assert resp.headers["cache-control"] == "no-store"


def test_put_valid_persists_version_and_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    repo = _override_runtime()
    resp = client.put("/v1/thresholds", json=_valid_body(), headers=_AUTH)
    assert resp.status_code == 201
    # Genau ein versionierter Satz angelegt (Supersession per INSERT).
    assert len(repo.all()) == 1
    # Audit: threshold_changed mit verknuepfter Satz-ID (NF-09) — schliesst Arashs Luecke.
    audit = repo.audit_entries()
    assert len(audit) == 1
    assert audit[0].event_type == AuditEventType.THRESHOLD_CHANGED
    assert audit[0].entity_id == repo.all()[0].id
    # Response traegt den angelegten Satz (mit id).
    assert resp.json()["changed_by"] == "operator-anr"


def test_put_invalid_thresholds_returns_422_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    _override_runtime()
    bad = asdict(load_thresholds())
    bad["betrieb"]["poll_interval_s"] = -5.0  # ungueltig -> ConfigError -> 422
    resp = client.put("/v1/thresholds", json=_valid_body(thresholds=bad), headers=_AUTH)
    assert resp.status_code == 422
    assert resp.json()["code"] == "UNPROCESSABLE_ENTITY"


def test_put_missing_changed_by_returns_422_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pflichtfeld changed_by fehlt -> RequestValidationError -> contract-konform 422.
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    _override_runtime()
    resp = client.put(
        "/v1/thresholds", json={"thresholds": asdict(load_thresholds())}, headers=_AUTH
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "UNPROCESSABLE_ENTITY"
    assert "detail" not in resp.json()


def test_put_non_ascii_key_returns_401_not_500(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression (#116): Nicht-ASCII-Token (U+00FC, latin-1-sendbar) -> 401, KEIN 500.
    monkeypatch.setenv(API_KEY_ENV, _KEY)
    _override_runtime()
    resp = client.put(
        "/v1/thresholds",
        json=_valid_body(),
        headers={"Authorization": b"Bearer schl\xfcssel"},  # noqa: E501
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_put_key_not_configured_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    _override_runtime()
    resp = client.put("/v1/thresholds", json=_valid_body(), headers=_AUTH)
    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


def test_put_repo_failure_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, _KEY)

    class _FailingRepo:
        def append(self, *_args, **_kwargs):
            raise RepositoryError("DB nicht verfuegbar")

    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(
        threshold_set_repo=_FailingRepo()
    )
    resp = client.put("/v1/thresholds", json=_valid_body(), headers=_AUTH)
    assert resp.status_code == 503
    assert resp.json()["code"] == "SERVICE_UNAVAILABLE"
