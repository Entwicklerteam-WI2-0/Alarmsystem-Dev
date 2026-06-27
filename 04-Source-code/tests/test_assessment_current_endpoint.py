"""Tests fuer GET /v1/assessment/current (DTB-43, G2->G3-Contract).

Belegt die Serving-Schicht gegen den **eingefrorenen Contract**
(docs/API_FROZEN_v1.md, openapi.yaml) und das **Fail-safe NF-01** an der
Lese-Grenze. Zwei Klassen von Sonderfaellen, bewusst getrennt:

- **Stale / Fault** (Daten da, aber veraltet/defekt) -> HTTP **200** mit
  `risk_level=unknown` (nie GRUEN). Kein Fehler (Contract: 503 NICHT fuer Stale).
- **Keine Daten / DB-Ausfall** (G2 nicht lieferfaehig) -> HTTP **503** mit dem
  Contract-Fehlerformat `Error {code, message}` (NICHT FastAPIs `{detail}`).

Reconciliation Jira-DoD <-> Frozen Contract: die DTB-43-Beschreibung nennt fuer
den DB-Ausfall woertlich `risk_level=unknown`. Der eingefrorene Contract bildet
einen internen Ausfall / "noch keine Daten" jedoch auf **503** ab
(`measured_at` ist auf 200 Pflicht und liegt bei DB-Ausfall gar nicht vor) ->
der Contract gewinnt (SoT). Dokumentiert im Lucas-Entscheidungslog.

Repos werden ueber die get_runtime-Dependency injiziert (app.dependency_overrides),
ohne DB und ohne Lifespan/Scheduler.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.exceptions import RuntimeNotReadyError
from src.config.loader import load_thresholds
from src.main import app, get_runtime
from src.model.enums import RiskLevel, SensorStatus
from src.model.schemas import Assessment, Reading
from src.storage.repository import RepositoryError

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Jeder Test setzt seine eigene Runtime; danach aufraeumen."""
    yield
    app.dependency_overrides.clear()


def _reading(
    measured_at: datetime,
    *,
    surface: float = 2.0,
    dew: float | None = 0.0,
    status: SensorStatus = SensorStatus.OK,
    rid: int | None = 1,
) -> Reading:
    return Reading(
        id=rid,
        sensor_id="anr-rwy-01",
        measured_at=measured_at,
        surface_temp_c=surface,
        air_temp_c=3.0,
        humidity_pct=80.0,
        received_at=measured_at,
        dew_point_c=dew,
        status=status,
    )


def _assessment(ts: datetime, risk: RiskLevel = RiskLevel.GREEN) -> Assessment:
    return Assessment(
        ts=ts,
        reading_id=1,
        risk_level=risk,
        surface_temp_c=2.0,
        dew_point_c=0.0,
        delta_t=2.0,
        humidity_pct=80.0,
    )


class _FakeAssessmentRepo:
    """Liefert ein vorbereitetes Assessment oder wirft (DB-Ausfall)."""

    def __init__(self, assessment: Assessment | None = None, *, error: bool = False) -> None:
        self._assessment = assessment
        self._error = error

    def get_latest(self) -> Assessment | None:
        if self._error:
            raise RepositoryError("assessment-DB nicht erreichbar")
        return self._assessment


class _FakeReadingRepo:
    """Liefert vorbereitete Readings oder wirft (DB-Ausfall)."""

    def __init__(self, readings: tuple[Reading, ...] = (), *, error: bool = False) -> None:
        self._readings = readings
        self._error = error

    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        # Beweist, dass der Endpoint _SENSOR_ID korrekt durchreicht — ein Tippfehler
        # in der Konstante wuerde hier auffallen (statt still ein leeres Ergebnis).
        assert sensor_id == "anr-rwy-01", f"unerwartete sensor_id: {sensor_id!r}"
        if self._error:
            raise RepositoryError("reading-DB nicht erreichbar")
        return self._readings[:limit]


def _override_runtime(
    *,
    assessment_repo: _FakeAssessmentRepo,
    reading_repo: _FakeReadingRepo,
) -> None:
    runtime = SimpleNamespace(
        thresholds=load_thresholds(),
        assessment_repo=assessment_repo,
        reading_repo=reading_repo,
    )
    app.dependency_overrides[get_runtime] = lambda: runtime


# ---------------------------------------------------------------------------
# 200 — Bewertung wird ausgeliefert (Gutfall + Serve-Zeit-Fail-safe)
# ---------------------------------------------------------------------------


def test_current_happy_path_returns_200_with_assessment():
    now = datetime.now(UTC)
    _override_runtime(
        assessment_repo=_FakeAssessmentRepo(_assessment(now, RiskLevel.GREEN)),
        reading_repo=_FakeReadingRepo((_reading(now),)),
    )

    response = client.get("/v1/assessment/current")

    assert response.status_code == 200
    # Echtzeit-Sicherheitsendpoint: kein Proxy/Browser darf den Momentan-Zustand cachen.
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["risk_level"] == "green"
    assert body["is_stale"] is False
    assert body["sensor_status"] == "ok"
    assert body["measured_at"] is not None
    assert body["surface_temp_c"] == 2.0


def test_current_stale_returns_200_unknown_and_is_stale():
    now = datetime.now(UTC)
    stale_timeout = load_thresholds().datenqualitaet.stale_timeout_s
    old = now - timedelta(seconds=stale_timeout + 60)
    _override_runtime(
        assessment_repo=_FakeAssessmentRepo(_assessment(old, RiskLevel.GREEN)),
        reading_repo=_FakeReadingRepo((_reading(old, surface=20.0, dew=0.0),)),
    )

    response = client.get("/v1/assessment/current")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"  # no-store auch auf Fail-safe-200
    body = response.json()
    assert body["risk_level"] == "unknown"  # nie GRUEN bei Stale (NF-01)
    assert body["is_stale"] is True
    assert body["surface_temp_c"] is None
    assert body["dew_point_c"] is None


def test_current_fault_returns_200_unknown():
    now = datetime.now(UTC)
    _override_runtime(
        assessment_repo=_FakeAssessmentRepo(_assessment(now, RiskLevel.GREEN)),
        reading_repo=_FakeReadingRepo((_reading(now, status=SensorStatus.FAULT),)),
    )

    response = client.get("/v1/assessment/current")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"  # no-store auch auf Fail-safe-200
    body = response.json()
    assert body["risk_level"] == "unknown"  # nie GRUEN bei fault (NF-01)
    assert body["sensor_status"] == "fault"
    assert body["is_stale"] is False
    # Invariante: genullte Messwerte treten bei unknown auf — auch auf dem Fault-Pfad.
    assert body["surface_temp_c"] is None
    assert body["dew_point_c"] is None
    assert body["delta_t"] is None
    assert body["humidity_pct"] is None


# ---------------------------------------------------------------------------
# 503 — G2 nicht lieferfaehig (DB-Ausfall + keine Daten), Error-Envelope
# ---------------------------------------------------------------------------


def _assert_503_error_envelope(response: httpx.Response) -> None:
    """503 MUSS exakt das Contract-Fehlerformat tragen: nur `{code, message}`.

    Die Set-Gleichheit der Keys beweist zugleich, dass weder FastAPIs `{detail}`
    noch eine Ampelfarbe (`risk_level`) durchschlaegt — ein Ausfall liefert nie
    GRUEN (NF-01). Separate `not in`-Asserts waeren daher redundant.
    """
    assert response.status_code == 503
    # 503 darf nicht von Proxies gecacht werden (sonst veralteter Ausfall-Zustand).
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body.keys()) == {"code", "message"}
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert isinstance(body["message"], str) and body["message"]


def test_current_db_failure_on_assessment_repo_returns_503():
    # Jira-DoD-Pfad (b): DB-Ausfall -> nie GRUEN. Contract: 503 (interner Ausfall).
    _override_runtime(
        assessment_repo=_FakeAssessmentRepo(error=True),
        reading_repo=_FakeReadingRepo((_reading(datetime.now(UTC)),)),
    )

    response = client.get("/v1/assessment/current")

    _assert_503_error_envelope(response)


def test_current_db_failure_on_reading_repo_returns_503():
    now = datetime.now(UTC)
    _override_runtime(
        assessment_repo=_FakeAssessmentRepo(_assessment(now, RiskLevel.GREEN)),
        reading_repo=_FakeReadingRepo(error=True),
    )

    response = client.get("/v1/assessment/current")

    _assert_503_error_envelope(response)


def test_current_no_data_returns_503():
    # Frischer Start: weder Bewertung noch Reading -> 503 (Contract, nicht null).
    _override_runtime(
        assessment_repo=_FakeAssessmentRepo(None),
        reading_repo=_FakeReadingRepo(()),
    )

    response = client.get("/v1/assessment/current")

    _assert_503_error_envelope(response)


def test_current_assessment_present_but_no_reading_returns_503():
    now = datetime.now(UTC)
    _override_runtime(
        assessment_repo=_FakeAssessmentRepo(_assessment(now, RiskLevel.GREEN)),
        reading_repo=_FakeReadingRepo(()),
    )

    response = client.get("/v1/assessment/current")

    _assert_503_error_envelope(response)


def test_current_unexpected_processing_error_returns_503_not_500(monkeypatch):
    # Daten liegen vor, aber die Aufbereitung scheitert. Den Fehler patchen wir DIREKT
    # in build_assessment_current (statt ihn ueber ein Implementierungsdetail wie
    # stale_timeout_s=0 -> is_stale-ValueError zu provozieren) -> der Test bleibt stabil,
    # egal wie sich die interne Validierung kuenftig verhaelt. Erwartung: 503 statt 500.
    now = datetime.now(UTC)
    _override_runtime(
        assessment_repo=_FakeAssessmentRepo(_assessment(now, RiskLevel.GREEN)),
        reading_repo=_FakeReadingRepo((_reading(now),)),
    )

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("unerwarteter Aufbereitungsfehler")

    monkeypatch.setattr("src.main.build_assessment_current", _boom)

    response = client.get("/v1/assessment/current")

    _assert_503_error_envelope(response)


# ---------------------------------------------------------------------------
# get_runtime — DI-Accessor (von den Endpoint-Tests via Override umgangen,
# daher hier direkt belegt: liest den Runtime-Graph aus app.state).
# ---------------------------------------------------------------------------


def test_get_runtime_reads_app_state():
    sentinel = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runtime=sentinel)))

    assert get_runtime(request) is sentinel


def test_get_runtime_raises_when_runtime_missing():
    # Fehlt app.state.runtime (lifespan nicht/teilweise durchlaufen), muss get_runtime
    # eine fangbare RuntimeNotReadyError werfen statt eines rohen AttributeError.
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(RuntimeNotReadyError):
        get_runtime(request)


def test_current_runtime_not_initialized_returns_503():
    # Kein dependency_override und keine Lifespan (der module-level TestClient laeuft ohne
    # Context-Manager) -> app.state.runtime ist NICHT gesetzt. get_runtime-Guard +
    # Exception-Handler muessen das contract-konform als 503 melden, nie als rohes 500.
    response = client.get("/v1/assessment/current")

    _assert_503_error_envelope(response)
