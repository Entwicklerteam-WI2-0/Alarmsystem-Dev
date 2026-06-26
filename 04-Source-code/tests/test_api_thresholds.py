"""Tests fuer GET /v1/thresholds (DTB-62, NF-05/NF-07-Lesen).

Prueft: Endpoint spiegelt die zur Laufzeit aktiven Schwellen (`runtime.thresholds` —
KEIN Disk-Read pro Request, eine Quelle der Wahrheit mit der Bewertungslogik), ist rein
lesend (RB-01-neutral), setzt `Cache-Control: no-store` und meldet bei nicht bereitem
Runtime fail-safe + contract-konform `Error {code, message}` (nicht FastAPI-`{detail}`).
"""

from dataclasses import asdict
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.runtime import get_runtime
from src.api.v1 import get_thresholds
from src.config.loader import (
    DatenqualitaetSchwellen,
    PlausibilitaetSchwellen,
    PrognoseSchwellen,
    Thresholds,
    VereisungsSchwellen,
    load_thresholds,
)
from src.main import RuntimeNotReadyError, app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Jeder Test setzt seine eigene Runtime/Dependency; danach aufraeumen."""
    yield
    app.dependency_overrides.clear()


def test_get_thresholds_returns_active_runtime_values():
    # Arrange: Runtime mit real geladenen Schwellen (wie nach build_runtime beim Start).
    app.dependency_overrides[get_runtime] = lambda: SimpleNamespace(thresholds=load_thresholds())
    # Act
    resp = client.get("/v1/thresholds")
    # Assert: 200 + Struktur aus thresholds.json, deckungsgleich mit dem Loader.
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"vereisung", "prognose", "datenqualitaet", "plausibilitaet"}
    assert body == asdict(load_thresholds())
    # Schwellen sind die Kalibrierung eines Fail-safe-Systems -> kein Proxy/Browser darf
    # ueberholte Werte ausliefern (NF-01-Geist, konsistent mit assessment/current).
    assert resp.headers["cache-control"] == "no-store"


def test_get_thresholds_reflects_runtime_not_hardcoded():
    # Arrange: Schwellen-Dependency mit bekannten Werten ueberschreiben.
    fake = Thresholds(
        vereisung=VereisungsSchwellen(1.0, 2.0, 3.0, 4.0),
        prognose=PrognoseSchwellen(9.0),
        datenqualitaet=DatenqualitaetSchwellen(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
        plausibilitaet=PlausibilitaetSchwellen(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
    )
    app.dependency_overrides[get_thresholds] = lambda: fake
    # Act
    resp = client.get("/v1/thresholds")
    # Assert: Endpoint gibt exakt die injizierten Werte zurueck -> kommt aus Runtime/Loader.
    assert resp.status_code == 200
    assert resp.json() == asdict(fake)


def test_get_thresholds_runtime_not_ready_returns_503_contract():
    # Arrange: Runtime nicht bereit (Start unvollstaendig / Config beim Start nicht ladbar).
    def _not_ready() -> object:
        raise RuntimeNotReadyError("test: runtime fehlt")

    app.dependency_overrides[get_runtime] = _not_ready
    # Act
    resp = client.get("/v1/thresholds")
    # Assert: Fail-safe 503 im Contract-Format Error{code,message} — NICHT {detail} —, no-store.
    assert resp.status_code == 503
    body = resp.json()
    assert body == {"code": "SERVICE_UNAVAILABLE", "message": "G2 momentan nicht lieferfaehig."}
    assert "detail" not in body  # FastAPI-Default {detail} wuerde die Naht brechen
    assert resp.headers["cache-control"] == "no-store"
