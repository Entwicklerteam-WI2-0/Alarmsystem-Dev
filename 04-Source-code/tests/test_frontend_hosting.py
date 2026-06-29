"""Tests fuer das statische Frontend-Hosting (G3-SPA via FastAPI StaticFiles).

G2 serviert das gebaute G3-Frontend (Vite-``dist/``) Same-Origin mit der API mit, gesteuert
ueber die Env ``G2_FRONTEND_DIR`` (``src.main._mount_frontend``). Geprueft wird die
Mount-Mechanik ISOLIERT auf einer Mini-App (fester ``/v1``-Stub + temporaeres ``dist/``),
damit kein Import-Zeitpunkt-Env-Konflikt mit der globalen ``src.main:app`` entsteht
(gleiches Muster wie ``test_cors.py``: eigene App statt Reimport).

Abgedeckt:
- SPA-Fallback: unbekannter Nicht-``/v1``-Pfad -> ``index.html`` (Client-Routing, Deep-Link/Reload)
- ``/v1``-Vorrang + ``/v1``-Ausschluss: echte API-Route gewinnt; unbekanntes ``/v1`` -> KEIN HTML
- Asset-Auslieferung
- No-op ohne / mit ungueltigem ``G2_FRONTEND_DIR`` (Tests/CI ohne Frontend bleiben gruen)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.main import _mount_frontend

_INDEX_MARKER = "SPA-ROOT-MARKER"
_INDEX_HTML = f'<!doctype html><html><body><div id="root">{_INDEX_MARKER}</div></body></html>'


def _make_dist(root: Path) -> Path:
    """Legt ein minimales Vite-``dist/``-Abbild an (index.html + ein Asset)."""
    (root / "index.html").write_text(_INDEX_HTML, encoding="utf-8")
    assets = root / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('frontend');", encoding="utf-8")
    return root


def _app_with_frontend(frontend_dir: Path | None, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """Mini-App mit fester ``/v1``-Route + (optional) gemountetem Frontend."""
    if frontend_dir is None:
        monkeypatch.delenv("G2_FRONTEND_DIR", raising=False)
    else:
        monkeypatch.setenv("G2_FRONTEND_DIR", str(frontend_dir))
    app = FastAPI()

    @app.get("/v1/health")
    def _health() -> dict[str, str]:
        return {"status": "ok"}

    _mount_frontend(app)
    return app


def test_root_serves_index_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app_with_frontend(_make_dist(tmp_path), monkeypatch)
    res = TestClient(app).get("/")
    assert res.status_code == 200
    assert _INDEX_MARKER in res.text


def test_deep_link_falls_back_to_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # React-Router-Deep-Link: /dashboard ist keine Datei -> index.html (Client-Routing).
    app = _app_with_frontend(_make_dist(tmp_path), monkeypatch)
    res = TestClient(app).get("/dashboard")
    assert res.status_code == 200
    assert _INDEX_MARKER in res.text


def test_api_route_takes_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # /v1/health ist eine echte Route -> JSON, NICHT index.html.
    app = _app_with_frontend(_make_dist(tmp_path), monkeypatch)
    res = TestClient(app).get("/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_unknown_v1_is_not_spa_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Unbekannter /v1-Pfad darf NICHT auf index.html umgebogen werden (API-404 bleibt API-404).
    app = _app_with_frontend(_make_dist(tmp_path), monkeypatch)
    res = TestClient(app).get("/v1/does-not-exist")
    assert res.status_code == 404
    assert _INDEX_MARKER not in res.text


def test_asset_is_served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app_with_frontend(_make_dist(tmp_path), monkeypatch)
    res = TestClient(app).get("/assets/app.js")
    assert res.status_code == 200
    assert "console.log" in res.text


def test_no_mount_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # G2_FRONTEND_DIR ungesetzt -> kein Mount: '/' existiert nicht (404), API laeuft normal.
    client = TestClient(_app_with_frontend(None, monkeypatch))
    assert client.get("/").status_code == 404
    assert client.get("/v1/health").status_code == 200


def test_no_mount_for_invalid_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Gesetzt, aber kein Verzeichnis -> No-op (kein Crash, nur Warnung).
    app = _app_with_frontend(tmp_path / "does-not-exist", monkeypatch)
    assert TestClient(app).get("/").status_code == 404
