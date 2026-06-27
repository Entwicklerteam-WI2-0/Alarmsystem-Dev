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

from fastapi.testclient import TestClient

from src.main import app

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
