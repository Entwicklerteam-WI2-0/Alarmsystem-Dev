"""Tests fuer den API-Key-Schutz schreibender v1-Endpoints (DTB-63, NF-07).

Der "Tuersteher" `require_api_key` laesst nur Requests mit gueltigem X-API-Key durch.
Fehlt der serverseitige Schluessel (Fehlkonfiguration), wird Schreibzugriff fail-safe
blockiert (503) statt versehentlich offen zu stehen.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.exceptions import ContractError
from src.api.security import API_KEY_ENV, require_api_key
from src.main import contract_error_handler

SECRET = "geheimes-test-token"  # noqa: S105 - synthetischer Testwert, kein echtes Secret


def _protected_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(ContractError, contract_error_handler)

    @app.post("/protected", dependencies=[Depends(require_api_key)])
    def protected() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv(API_KEY_ENV, SECRET)
    return TestClient(_protected_app())


def test_valid_key_allows_access(client):
    resp = client.post("/protected", headers={"X-API-Key": SECRET})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_missing_key_is_rejected(client):
    resp = client.post("/protected")
    assert resp.status_code == 401
    body = resp.json()
    assert body == {"code": "UNAUTHORIZED", "message": "Ungueltiger oder fehlender API-Key"}
    assert resp.headers["cache-control"] == "no-store"


def test_wrong_key_is_rejected(client):
    resp = client.post("/protected", headers={"X-API-Key": "falsch"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_unconfigured_server_denies_writes(monkeypatch):
    # Kein serverseitiger Schluessel gesetzt -> Schreibzugriff fail-safe blockiert.
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    client = TestClient(_protected_app())
    resp = client.post("/protected", headers={"X-API-Key": "egal"})
    assert resp.status_code == 503
    assert resp.json() == {
        "code": "SERVICE_UNAVAILABLE",
        "message": "Schreibzugriff nicht konfiguriert",
    }
    assert resp.headers["cache-control"] == "no-store"
