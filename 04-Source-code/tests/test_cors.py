"""Tests fuer die CORS-Middleware (C1, Vorbereitung G3-Browser-Integration / DTB-23).

G3 ist ein Browser-Frontend von ANDERER Origin (eigener Host/Port). Ohne CORS-Header
blockt der Browser per Same-Origin-Policy JEDEN Call von G3 an G2 — Server-zu-Server und
die pytest-Suite sind davon unberuehrt, die echte UI aber nicht. Diese Tests sichern, dass
die Header gesetzt werden: einfacher GET (mit Origin) + Preflight-OPTIONS.

Default ist bewusst "*" (abgeschlossener Prototyp/Intranet); pro Umgebung per
G2_CORS_ORIGINS einschraenkbar. Die App wird bei Import gebaut -> die Tests pruefen den
Default-Zustand (deterministisch, ohne Env-Manipulation). Die CORS-Header werden von der
Middleware unabhaengig vom 200/503-Pfad gesetzt, daher braucht es keine Runtime-Override.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from src.main import _cors_origins, app

client = TestClient(app)

_ORIGIN = "http://g3-frontend.test"


def test_simple_get_has_cors_allow_origin_header():
    # Act: GET mit Origin-Header (so wie ein Browser ihn cross-origin sendet).
    response = client.get("/v1/health", headers={"Origin": _ORIGIN})

    # Assert: CORS-Header gesetzt -> der Browser laesst die Antwort durch.
    # Default "*" -> allow-origin == "*" (Statuscode hier bewusst nicht gekoppelt).
    assert response.headers.get("access-control-allow-origin") == "*"


def test_preflight_options_allows_contract_methods():
    # Act: Browser-Preflight vor einem "komplexen" Request (z. B. POST /ack).
    response = client.options(
        "/v1/assessment/current",
        headers={
            "Origin": _ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    # Assert: Preflight beantwortet (200) + erlaubte Origin/Methoden gemeldet.
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods and "GET" in allow_methods


def test_cors_origins_empty_falls_back_to_wildcard(monkeypatch):
    # Edge-Case (Review MEDIUM): leeres `G2_CORS_ORIGINS=` existiert als Wert und umgeht den
    # Default -> darf CORS NICHT still sperren, sondern wie "nicht gesetzt" auf "*" zurueckfallen.
    monkeypatch.setenv("G2_CORS_ORIGINS", "")
    assert _cors_origins() == ["*"]


def test_cors_origins_parses_comma_separated_list(monkeypatch):
    monkeypatch.setenv("G2_CORS_ORIGINS", " http://a.test , http://b.test ")
    assert _cors_origins() == ["http://a.test", "http://b.test"]


def test_cors_origins_wildcard_dominates_mixed_list(monkeypatch):
    # Edge-Case (Review LOW): "*" zusammen mit konkreten Origins -> Wildcard dominiert (["*"]),
    # statt einer ueberraschenden Mischliste durchzureichen.
    monkeypatch.setenv("G2_CORS_ORIGINS", "*,http://g3.local")
    assert _cors_origins() == ["*"]


def test_restricted_origins_block_foreign_origin(monkeypatch):
    # Negativtest (Review LOW): bei eingeschraenkten Origins bekommt eine FREMDE Origin KEINEN
    # allow-origin-Header. Isolierte App mit _cors_origins() unter gesetzter Env (kein Reimport
    # der globalen App noetig, daher keine Suite-Seiteneffekte).
    monkeypatch.setenv("G2_CORS_ORIGINS", "http://allowed.test")
    restricted = FastAPI()
    restricted.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @restricted.get("/ping")
    def _ping() -> dict[str, bool]:
        return {"ok": True}

    local_client = TestClient(restricted)

    allowed = local_client.get("/ping", headers={"Origin": "http://allowed.test"})
    assert allowed.headers.get("access-control-allow-origin") == "http://allowed.test"

    foreign = local_client.get("/ping", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in foreign.headers
