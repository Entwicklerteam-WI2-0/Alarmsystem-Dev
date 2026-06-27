"""E2E Fail-safe ueber den API-Pfad (DTB-49).

Belegt NF-01 ueber die VOLLE Pipeline (AssessmentService + echte In-Memory-Repos ->
GET /v1/assessment/current): stale- oder fault-Daten fuehren nie zu GRUEN, sondern zu
risk_level=unknown mit genullten Messwerten.

Mehrwert gegenueber test_assessment_current_endpoint.py: jener prueft den Endpoint mit
Fakes (Stale Z. 146-163, Fault Z. 166-185); hier laeuft der echte Service + die echten
Repos durch — der vollstaendige Wire-Contract-Pfad, nicht der Endpoint isoliert.

Zeit ist deterministisch: der Stale-Fall waehlt measured_at relativ zur echten Uhr; der
Serve-Zeit-Fall patcht src.main.datetime, um die Serve-Uhr kontrolliert vorzustellen
(zeigt: ein gespeichertes GRUEN wird zur Abfragezeit zu unknown).
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.assessment.service import AssessmentService
from src.main import Runtime, app, get_runtime
from src.model.enums import RiskLevel, SensorStatus
from src.model.schemas import Assessment, Reading
from src.storage.repository import InMemoryReadingRepository

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_overrides_and_state():
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "runtime"):
            del app.state.runtime


def _reading(
    measured_at: datetime,
    *,
    surface: float = 5.0,
    dew: float | None = 0.0,
    status: SensorStatus = SensorStatus.OK,
) -> Reading:
    # Default-Werte ergaeben FRISCH+OK ein GRUEN (T_s=5.0>1.0, delta_t=5.0>1.0) -> der
    # Fail-safe muss dieses GRUEN bei stale/fault aktiv ueberstimmen (NF-01).
    return Reading(
        sensor_id="anr-rwy-01",
        measured_at=measured_at,
        surface_temp_c=surface,
        air_temp_c=5.0,
        humidity_pct=50.0,
        received_at=measured_at,
        dew_point_c=dew,
        status=status,
    )


def _persist_and_assess(
    reading_repo: InMemoryReadingRepository,
    service: AssessmentService,
    reading: Reading,
    now: datetime,
) -> Assessment:
    # Spiegelt den realen Pfad: Reading persistieren (id vergeben), dann bewerten.
    new_id = reading_repo.save(reading)
    return service.assess_reading(reading.model_copy(update={"id": new_id}), now)


def _fixed_datetime(value: datetime) -> type:
    # Minimaler datetime-Ersatz fuer src.main: nur .now(tz) wird im Endpoint genutzt.
    class _Fixed:
        @staticmethod
        def now(_tz: object = None) -> datetime:
            return value

    return _Fixed


def test_stale_reading_returns_unknown_not_green(runtime: Runtime) -> None:
    now = datetime.now(UTC)
    stale_timeout = runtime.thresholds.datenqualitaet.stale_timeout_s
    old = now - timedelta(seconds=stale_timeout + 60)
    # Warmes (waere GRUEN) aber veraltetes Reading durch die volle Pipeline.
    _persist_and_assess(runtime.reading_repo, runtime.service, _reading(old), now)

    app.dependency_overrides[get_runtime] = lambda: runtime
    response = client.get("/v1/assessment/current")

    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "unknown"  # nie GRUEN bei Stale (NF-01)
    assert body["is_stale"] is True
    assert body["surface_temp_c"] is None
    assert body["dew_point_c"] is None
    assert body["delta_t"] is None
    assert body["humidity_pct"] is None


def test_serve_time_stale_returns_unknown_not_green(
    runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    stale_timeout = runtime.thresholds.datenqualitaet.stale_timeout_s
    # Reading ist zur ASSESS-Zeit frisch -> ein GRUEN-Assessment wird gespeichert.
    assessment = _persist_and_assess(runtime.reading_repo, runtime.service, _reading(now), now)
    assert assessment.risk_level == RiskLevel.GREEN  # wirklich GRUEN persistiert

    # Serve-Uhr kontrolliert vorstellen: derselbe Snapshot ist nun veraltet.
    advanced = now + timedelta(seconds=stale_timeout + 60)
    monkeypatch.setattr("src.main.datetime", _fixed_datetime(advanced))

    app.dependency_overrides[get_runtime] = lambda: runtime
    response = client.get("/v1/assessment/current")

    assert response.status_code == 200
    body = response.json()
    # Trotz gespeichertem GRUEN -> Serve-Zeit-Fail-safe erzwingt unknown (NF-01).
    assert body["risk_level"] == "unknown"
    assert body["is_stale"] is True
    assert body["surface_temp_c"] is None


def test_fault_reading_returns_unknown_not_green(runtime: Runtime) -> None:
    now = datetime.now(UTC)
    # Frisches, warmes Reading (waere GRUEN), aber der Sensor meldet fault.
    _persist_and_assess(
        runtime.reading_repo,
        runtime.service,
        _reading(now, surface=20.0, status=SensorStatus.FAULT),
        now,
    )

    app.dependency_overrides[get_runtime] = lambda: runtime
    response = client.get("/v1/assessment/current")

    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "unknown"  # nie GRUEN bei fault (NF-01)
    assert body["sensor_status"] == "fault"
    assert body["is_stale"] is False
    assert body["surface_temp_c"] is None
    assert body["dew_point_c"] is None
