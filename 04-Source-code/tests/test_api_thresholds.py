"""Tests fuer GET /v1/thresholds (DTB-62, NF-05/NF-07-Lesen).

Prueft: Endpoint liefert die Schwellen aus dem Loader (DTB-15) — NICHT hardcodiert —,
ist rein lesend (RB-01-neutral) und reagiert bei kaputter Config fail-safe ohne Leak.
"""

from dataclasses import asdict
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.v1 import get_thresholds
from src.config.loader import (
    ConfigError,
    DatenqualitaetSchwellen,
    PlausibilitaetSchwellen,
    PrognoseSchwellen,
    Thresholds,
    VereisungsSchwellen,
    load_thresholds,
)
from src.main import app

client = TestClient(app)


def test_get_thresholds_returns_loader_values():
    # Act
    resp = client.get("/v1/thresholds")
    # Assert: 200 + Struktur aus thresholds.json, deckungsgleich mit dem Loader.
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"vereisung", "prognose", "datenqualitaet", "plausibilitaet"}
    assert body == asdict(load_thresholds())


def test_get_thresholds_reflects_loader_not_hardcoded():
    # Arrange: Loader-Abhaengigkeit mit bekannten Werten ueberschreiben.
    fake = Thresholds(
        vereisung=VereisungsSchwellen(1.0, 2.0, 3.0, 4.0),
        prognose=PrognoseSchwellen(9.0),
        datenqualitaet=DatenqualitaetSchwellen(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
        plausibilitaet=PlausibilitaetSchwellen(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
    )
    app.dependency_overrides[get_thresholds] = lambda: fake
    try:
        # Act
        resp = client.get("/v1/thresholds")
        # Assert: Endpoint gibt exakt die injizierten Werte zurueck -> kommt aus dem Loader.
        assert resp.status_code == 200
        assert resp.json() == asdict(fake)
    finally:
        app.dependency_overrides.clear()


def test_get_thresholds_config_error_returns_503_without_leak():
    # Arrange: Loader scheitert (z. B. Config fehlt/kaputt).
    with patch("src.api.v1.load_thresholds", side_effect=ConfigError("interner pfad /geheim")):
        # Act
        resp = client.get("/v1/thresholds")
    # Assert: sauberer 503 (Fail-safe), interne Details werden NICHT geleakt.
    assert resp.status_code == 503
    assert "geheim" not in resp.text


def test_get_thresholds_os_error_returns_503_without_leak():
    # Arrange: Loader scheitert mit Berechtigungs-/Lese-Fehler (OSError).
    with patch("src.api.v1.load_thresholds", side_effect=PermissionError("/etc/secret")):
        # Act
        resp = client.get("/v1/thresholds")
    # Assert: sauberer 503 (Fail-safe), interne Details werden NICHT geleakt.
    assert resp.status_code == 503
    assert "/etc/secret" not in resp.text
