"""Fail-safe-Integrationstests je Schicht (DTB-49, ADR E-40, NF-01).

Pro Schicht ein benannter Integrationstest durch den echten Pfad (echte
In-Memory-Repos + echter AssessmentService / build_assessment_current /
GET /v1/assessment/current-Endpoint). Beweist: bei der beschriebenen
Fehlerbedingung liefert das System NIE `risk_level=green` aus.

Schichten (ADR E-40):
  Schicht 1 Stale          — Reading veraltet (measured_at > stale_timeout_s)
                             -> AssessmentService -> unknown, nie GRUEN
  Schicht 2 Sensor-Fault   — reading.status=fault
                             -> AssessmentService -> unknown, nie GRUEN
  Schicht 3 Plausibilitaet — Wert ausserhalb plausibler Grenzen (Poller-Validierung)
                             -> Poller gibt None -> Service -> unknown, nie GRUEN
  Schicht 4 DB-Ausfall     — RepositoryError bei get_latest
                             -> HTTP 503, Contract-Fehlerformat, nie GRUEN
  Schicht 5 Kaskade        — dew_point_c=None bei T_s <= Gefrierpunkt (E-34)
                             -> assess_ice_risk -> mind. ORANGE, nie GRUEN, nie unknown
  Schicht 6 Serve-Zeit     — gespeichertes GRUEN altert bis stale_timeout ablaeuft
                             -> build_assessment_current -> unknown, nie GRUEN

Schicht 2 hat zwei Tests:
  Schicht 2  (Defense-in-Depth) — fault-Reading direkt am Service -> unknown.
  Schicht 2a (REALER Pfad)      — G1 meldet status=fault -> Poller poll() = None
                                  (HTTP gemockt) -> Service -> unknown. Belegt den
                                  tatsaechlichen Produktionsfluss (im realen Fluss
                                  erreicht ein fault-Reading den Service-fault-Zweig
                                  nie, weil der Poller es vorher verwirft).

Mehrwert:
  - Alle sechs E-40-Schichten sind explizit benannt und maschinell geprueft.
  - Schicht 2a belegt den ECHTEN Fault-Pfad (Poller -> None), nicht nur die
    Defense-in-Depth-Linie im Service (toter Service-Zweig im aktuellen Fluss).
  - Schicht 3 testet den Poller-Validierungspfad ueber die Public-API poll() (HTTP gemockt).
    Achtung: check_plausibility (Sprung/Flatline) ist NICHT verdrahtet (toter Code)
    -> braucht bei Verdrahtung einen eigenen Test (Doc am Test).
  - Schicht 4 ist ein neuer Fall: DB-Ausfall -> 503; parametrisiert ueber BEIDE
    DB-Lesepfade (assessment_repo UND reading_repo).
  - Schicht 6 testet build_assessment_current direkt (nicht via HTTP-Endpoint),
    ergaenzend zu test_e2e_failsafe_api.py (dort via TestClient + monkeypatch).

Konventionen:
  - Keine Schwellen-Hardcodes: alle Werte aus `load_thresholds()` (NF-05).
  - Alle Repos sind In-Memory-Doubles (keine DB-Verbindung noetig).
  - conftest.py-Fixtures (runtime, assessment_service, thresholds, ...) werden
    wiederverwendet; keine doppelten Fixtures gleichen Namens.

Referenzen: NF-01, RB-01, E-34, E-36, E-40, DTB-13, DTB-43, DTB-49, DTB-64.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.assessment.service import AssessmentService, build_assessment_current
from src.config.loader import Thresholds
from src.ingest.poller import Poller
from src.main import Runtime, app, get_runtime
from src.model.enums import RiskLevel, SensorStatus
from src.model.schemas import Assessment, Reading
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.repository import InMemoryReadingRepository, RepositoryError


@pytest.fixture
def client() -> TestClient:
    """TestClient gegen die echte ASGI-App fuer die API-Tests (Schicht 4).

    Bewusst als Fixture (nicht modul-global), damit kein geteilter Client-State zwischen
    Tests leckt. Jeder API-Test MUSS den Runtime via app.dependency_overrides[get_runtime]
    setzen; ohne Override liefe die echte lifespan (build_runtime -> DB/G1) und der Test
    schluege mit 503 fehl. Die autouse-Fixture _cleanup_app_state raeumt overrides +
    app.state nach jedem Test (Test-Isolation).
    """
    return TestClient(app)


# ---------------------------------------------------------------------------
# Stub fuer DB-Ausfall-Simulation (Schicht 4, E-40)
# ---------------------------------------------------------------------------


class _AssessmentRepoDBFehler(InMemoryAssessmentRepository):
    """In-Memory-Stub, dessen get_latest immer RepositoryError wirft.

    Simuliert einen DB-Ausfall (Verbindungsabbruch / OperationalError) an genau
    der Stelle, die GET /v1/assessment/current zuerst aufruft (E-40 Schicht 4).
    save() bleibt intakt, damit der Service unbehelligt schreibt (falls noetig).
    """

    def get_latest(self) -> Assessment | None:
        raise RepositoryError("Test-Stub: DB ausgefallen (Schicht 4, E-40)")


class _ReadingRepoDBFehler(InMemoryReadingRepository):
    """In-Memory-Stub, dessen get_latest immer RepositoryError wirft.

    Gegenstueck zu _AssessmentRepoDBFehler fuer den ZWEITEN DB-Lesepfad im
    Endpoint (reading_repo.get_latest in GET /v1/assessment/current, main.py). Belegt,
    dass derselbe except-Block auch hier fail-safe auf 503 abbildet (E-40 Schicht 4).
    """

    def get_latest(self, sensor_id: str, limit: int = 1) -> Sequence[Reading]:
        raise RepositoryError("Test-Stub: DB ausgefallen beim Reading-Read (Schicht 4, E-40)")


def _ok_health_response() -> Mock:
    """Mock fuer eine erfolgreiche GET /health-Antwort (200, raise_for_status no-op)."""
    response = Mock()
    response.raise_for_status.return_value = None
    return response


def _current_response(payload: dict) -> Mock:
    """Mock fuer eine GET /current-Antwort mit dem uebergebenen JSON-Payload (200)."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _mock_g1_get(current_payload: dict) -> Mock:
    """Baut einen httpx.get-Ersatz, der /health (200) und /current (payload) beantwortet.

    Spiegelt das Mock-Muster aus test_ingest.py (_mock_get_for): der Poller fragt
    erst /health (muss 200 sein, sonst kein /current) und dann /current ab.
    """

    def side_effect(url: str, **_kwargs: object) -> Mock:
        if url.endswith("/health"):
            return _ok_health_response()
        if url.endswith("/current"):
            return _current_response(current_payload)
        raise ValueError(f"Unerwartete URL im Poller-Mock: {url}")

    return Mock(side_effect=side_effect)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _g1_iso(moment: datetime) -> str:
    """Formatiert einen UTC-Zeitpunkt als G1-Wire-Zeitstempel (ISO-8601, Z-Suffix).

    Eine Quelle fuer das Format, das G1 in GET /current liefert (sekundengenau, UTC) —
    statt das Strftime-Muster je Payload zu wiederholen.
    """
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _save_and_get_reading(
    reading_repo: InMemoryReadingRepository,
    reading: Reading,
) -> Reading:
    """Spiegelt den Poller-Pfad: Reading speichern, mit vergebener id zurueckgeben.

    Stellt die DTB-28-Invariante her (reading.id != None auf dem Gutfall-Pfad),
    damit assess_reading den Happy-Path durchlaeuft und nicht vorzeitig mit
    ValueError abbricht.
    """
    new_id = reading_repo.save(reading)
    return reading.model_copy(update={"id": new_id})


def _gruen_kandidat(sensor_id: str, measured_at: datetime, thresholds: Thresholds) -> Reading:
    """Gibt ein Reading zurueck, das bei frischem OK-Sensor GRUEN ergeben wuerde.

    T_s und T_d werden relativ zu den Config-Schwellen berechnet (NF-05, keine
    Hardcodes). Bei den Default-Schwellen (t_s_gefrierpunkt=0, t_s_gelb=1.0,
    delta_t_feucht=1.0): surface=4.0, dew=2.0, delta_t=2.0 -> GRUEN.

    Invariante (kommentiert, nicht assertiert, da assess_ice_risk hier nicht
    aufgerufen wird):
      T_s > max(gefrierpunkt, gelb_auffang) -> kein ROT/ORANGE/GELB durch Temp
      delta_t = T_s - T_d = delta_t_feucht + 1.0 > delta_t_feucht -> nicht humid
      dew_point_c != None -> kein GELB-Fallback
      -> GRUEN
    """
    v = thresholds.vereisung
    # Relative Offsets (+3.0 / +1.0 K) auf die Config-Schwellen, kein Hardcode (NF-05). Bei
    # extrem engen externen Schwellen koennte daraus kein echtes GRUEN entstehen — der
    # Precondition-Assert in Schicht 6 faengt genau diesen Fall explizit ab.
    # Deutlich ueber beiden Untergrenz-Schwellen, damit T_s kein GELB ausloest.
    surface = max(v.t_s_gefrierpunkt_c, v.t_s_gelb_auffang_c) + 3.0
    # Taupunkt so weit unter T_s, dass delta_t > delta_t_feucht_k (trockene Oberflaeche).
    dew = surface - (v.delta_t_feucht_k + 1.0)
    return Reading(
        sensor_id=sensor_id,
        measured_at=measured_at,
        surface_temp_c=surface,
        air_temp_c=surface + 1.0,
        humidity_pct=50.0,
        received_at=measured_at,
        dew_point_c=dew,
        status=SensorStatus.OK,
    )


# ---------------------------------------------------------------------------
# Cleanup-Fixture fuer App-State nach API-Tests (autouse: laeuft fuer alle Tests;
# bei reinen Service-Tests ist die Bereinigung eine No-Op und schadet nicht).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup_app_state() -> Iterator[None]:
    """Setzt app.dependency_overrides und app.state nach jedem Test zurueck.

    Notwendig fuer die API-Tests (Schicht 4), damit ein ueberschriebener
    Runtime nicht in den naechsten Test leckt. Bei Service-level-Tests
    ist dieser Cleanup eine No-Op.
    """
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "runtime"):
            del app.state.runtime


# ---------------------------------------------------------------------------
# Schicht 1 — Stale (ADR E-40 §1, Fundstelle: failsafe.is_stale + service.py)
# ---------------------------------------------------------------------------


def test_schicht1_stale_assess_zeit_nie_gruen(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    assessment_service: AssessmentService,
    thresholds: Thresholds,
    sensor_id: str,
) -> None:
    """E-40 Schicht 1: veraltetes Reading -> AssessmentService -> unknown, nie GRUEN (NF-01).

    Belegt: is_stale greift in AssessmentService.assess_reading VOR assess_ice_risk.
    Das Reading haette GRUEN ergeben, wenn es frisch waere — das Fail-safe ueberstimmt
    den Messwert aufgrund des Alters. Das ausloesende Reading wird verknuepft
    (Audit-Traceability, NF-05).
    """
    now = datetime.now(UTC)
    stale_timeout_s = thresholds.datenqualitaet.stale_timeout_s
    old_ts = now - timedelta(seconds=stale_timeout_s + 60)

    # Kandidat, der GRUEN ergeben wuerde — wenn er frisch waere.
    reading = _gruen_kandidat(sensor_id, old_ts, thresholds)
    reading_mit_id = _save_and_get_reading(reading_repo, reading)

    result = assessment_service.assess_reading(reading_mit_id, now)

    # E-40 Schicht 1: Stale -> unknown, nie GRUEN (NF-01)
    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.reading_id == reading_mit_id.id  # ausloesendes Reading verknuepft
    persisted = assessment_repo.get_latest()
    assert persisted is not None
    assert persisted.risk_level is RiskLevel.UNKNOWN


# ---------------------------------------------------------------------------
# Schicht 2 — Sensor-Fault (ADR E-40 §2, Fundstelle: service.py DTB-64)
# ---------------------------------------------------------------------------


def test_schicht2_sensor_fault_nie_gruen(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    assessment_service: AssessmentService,
    thresholds: Thresholds,
    sensor_id: str,
) -> None:
    """E-40 Schicht 2 (Defense-in-Depth): reading.status=fault am Service -> unknown, nie GRUEN.

    WICHTIG — dies testet einen Defense-in-Depth-Pfad, NICHT den realen Fluss:
    Im Produktionsfluss verwirft bereits der Poller ein fault-Reading
    (poller._build_reading Z. ~181-183 -> poll() gibt None zurueck), sodass der
    Service in der Praxis `None` (nicht ein fault-Reading) erhaelt. Der
    `elif reading.status is FAULT`-Zweig in service.py (~Z. 100) ist daher im
    aktuellen Single-Poller-Fluss nicht direkt erreichbar — er bleibt aber als
    zweite Verteidigungslinie wichtig (kuenftige Aufrufer/Sensor-Quellen, die ein
    fault-Reading direkt durchreichen). Dieser Test sichert genau diese Linie ab.

    Den REALEN Fault-Pfad (Poller -> None -> Service -> unknown) belegt
    `test_schicht2a_fault_realer_poller_pfad_liefert_none` unten.

    Belegt hier: der Sensor-Fault-Zweig in AssessmentService greift VOR der
    regulaeren Kaskade. Messwerte koennen GRUEN anzeigen — fault ueberstimmt sie
    (NF-01). Das ausloesende Reading wird verknuepft (NF-05).
    """
    now = datetime.now(UTC)
    # Frisches Reading mit GRUEN-Werten, aber Sensor meldet fault.
    reading = _gruen_kandidat(sensor_id, now, thresholds).model_copy(
        update={"status": SensorStatus.FAULT}
    )
    reading_mit_id = _save_and_get_reading(reading_repo, reading)

    result = assessment_service.assess_reading(reading_mit_id, now)

    # E-40 Schicht 2: fault -> unknown, nie GRUEN (NF-01)
    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.reading_id == reading_mit_id.id  # ausloesendes Reading verknuepft
    persisted = assessment_repo.get_latest()
    assert persisted is not None
    assert persisted.risk_level is RiskLevel.UNKNOWN


def test_schicht2a_fault_realer_poller_pfad_liefert_none(
    poller: Poller,
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    assessment_service: AssessmentService,
    sensor_id: str,
) -> None:
    """E-40 Schicht 2 (REALER Pfad): G1 meldet status=fault -> Poller None -> Service unknown.

    Belegt den TATSAECHLICHEN Produktionsfluss (im Gegensatz zum Defense-in-Depth-
    Test oben): G1 liefert via GET /current ein Snapshot mit `status=fault` ->
    poller._build_reading verwirft es fail-safe -> poll() gibt None zurueck (kein
    Reading wird persistiert) -> AssessmentService.assess_reading(None) -> unknown,
    nie GRUEN (NF-01). Damit ist die E-40-Schicht-2-Bedingung Ende-zu-Ende belegt.

    Die HTTP-Schicht (G1 ist external) wird ueber das Mock-Muster aus test_ingest.py
    gestellt: /health 200, /current liefert den fault-Payload. Die Plausibilitaets-/
    Stale-Schwellen kommen aus der echten Config (poller-Fixture, NF-05).
    """
    now = datetime.now(UTC)
    # G1-Snapshot mit GRUEN-Werten, aber status=fault. measured_at frisch (kein Stale),
    # damit AUSSCHLIESSLICH die fault-Bedingung den Verwurf ausloest.
    fault_payload = {
        "sensor_id": sensor_id,
        "measured_at": _g1_iso(now),
        "surface_temp_c": 5.0,
        "air_temp_c": 6.0,
        "humidity_pct": 50.0,
        "status": "fault",
    }

    # Schicht 2a (real): Poller pollt G1 -> fault -> None (kein Reading persistiert)
    with patch("src.ingest.poller.httpx.get", _mock_g1_get(fault_payload)):
        reading = poller.poll()

    assert reading is None, (
        "Poller muss ein G1-Snapshot mit status=fault verwerfen (E-40 Schicht 2, realer Pfad)"
    )
    # Invariante (conftest): die reading_repo-Fixture und poller.repository sind DIESELBE
    # In-Memory-Instanz (poller-Fixture: repository=reading_repo). Nur dann beweist diese
    # Assertion, dass der Poller nichts persistiert hat. Wird die Fixture-Hierarchie je
    # entkoppelt (eigener Poller-Repo), muss diese Assertion mitgezogen werden.
    assert reading_repo.get_latest(sensor_id, limit=1) == ()

    # Schicht 2a (real, Forts.): Service bewertet None -> unknown, nie GRUEN (NF-01)
    result = assessment_service.assess_reading(reading, now)
    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.reading_id is None  # kein Reading-Bezug moeglich (poll() lieferte None)
    persisted = assessment_repo.get_latest()
    assert persisted is not None
    assert persisted.risk_level is RiskLevel.UNKNOWN


def test_schicht1_und_2_fault_und_stale_gleichzeitig_nie_gruen(
    reading_repo: InMemoryReadingRepository,
    assessment_service: AssessmentService,
    thresholds: Thresholds,
    sensor_id: str,
) -> None:
    """E-40 Schicht 1+2: gleichzeitig fault UND stale -> unknown, nie GRUEN (NF-01).

    Sichert die Reihenfolge-Invariante in service.assess_reading ab: der
    fault-Zweig (Z. 100) wird VOR dem stale-Zweig (Z. 107) geprueft. Treffen
    beide Bedingungen zu, darf das System weder GRUEN noch crashen, sondern
    muss fail-safe unknown liefern. Der Test fixiert, dass eine Umsortierung
    der Branches den Fail-safe nicht still bricht.
    """
    now = datetime.now(UTC)
    stale_timeout_s = thresholds.datenqualitaet.stale_timeout_s
    old_ts = now - timedelta(seconds=stale_timeout_s + 60)
    # Reading ist gleichzeitig veraltet (old_ts) UND meldet fault.
    reading = _gruen_kandidat(sensor_id, old_ts, thresholds).model_copy(
        update={"status": SensorStatus.FAULT}
    )
    reading_mit_id = _save_and_get_reading(reading_repo, reading)

    result = assessment_service.assess_reading(reading_mit_id, now)

    # fault UND stale gleichzeitig -> unknown, nie GRUEN (NF-01)
    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.reading_id == reading_mit_id.id
    # Persistenz-Assertion bewusst weggelassen: dieser Test fokussiert die Branch-Reihenfolge
    # (fault VOR stale) im Service; die Repo-Persistenz decken Schicht 1 + Schicht 2 ab.


# ---------------------------------------------------------------------------
# Schicht 3 — Plausibilitaet (ADR E-40 §3, Fundstelle: Poller._build_reading)
# ---------------------------------------------------------------------------


def test_schicht3_plausibilitaet_ausserhalb_grenzen_nie_gruen(
    poller: Poller,
    assessment_repo: InMemoryAssessmentRepository,
    assessment_service: AssessmentService,
    thresholds: Thresholds,
    sensor_id: str,
) -> None:
    """E-40 Schicht 3: Wert ausserhalb plausibler Grenzen -> Poller None -> unknown, nie GRUEN.

    Beweist zwei Real-Pfad-Stufen ueber die Public-API (G1-HTTP gemockt wie Schicht 2a):
    a) poll() verwirft surface_temp_c > plausibilitaet.max_temp_c -> None (keine Persistenz).
    b) AssessmentService.assess_reading(reading=None) -> unknown (NF-01).
    Die Plausibilitaetsgrenzen kommen aus config/thresholds.json (NF-05, kein Hardcode).

    SCOPE-HINWEIS (wichtig): E-40 §3 nennt als Auslöser auch "Sprung / Flatline /
    Zeitstempelfehler" -> `check_plausibility` (src/assessment/failsafe.py). Diese
    Sprung-/Flatline-Funktion ist zwar implementiert und unit-getestet (test_failsafe.py),
    aber AKTUELL in KEINEM Produktionscode verdrahtet (weder Poller noch Service rufen
    sie auf — verifiziert per grep). Dieser Test deckt daher AUSSCHLIESSLICH die real
    aktive Schicht-3-Stufe ab: die Bereichs-/Range-Validierung im Poller (_build_reading).
    Sobald `check_plausibility` in den Produktionsfluss eingebunden wird (separater Task,
    NICHT Teil von DTB-49), MUSS ein eigener Integrationstest fuer den Sprung-/Flatline-
    Pfad ergaenzt werden (G1 liefert zwei Snapshots mit unplausiblem Sprung -> unknown).
    """
    now = datetime.now(UTC)
    max_temp = thresholds.plausibilitaet.max_temp_c

    # G1-Payload mit surface_temp_c klar ausserhalb der Obergrenze.
    payload: dict[str, object] = {
        "sensor_id": sensor_id,
        "measured_at": _g1_iso(now),
        "surface_temp_c": max_temp + 10.0,  # klar jenseits der Plausibilitaetsgrenze
        "air_temp_c": 5.0,
        "humidity_pct": 80.0,
        "status": "ok",
    }

    # Schicht 3a: Poller pollt G1 -> Plausibilitaetspruefung verwirft -> None (keine Persistenz).
    # Ueber die PUBLIC API poll() (HTTP gemockt wie Schicht 2a, /health 200 + /current payload),
    # nicht ueber die private _build_reading -> testet den realen Pfad und bleibt
    # refactoring-robust (kein Zugriff auf Implementierungsdetails).
    with patch("src.ingest.poller.httpx.get", _mock_g1_get(payload)):
        reading = poller.poll()
    assert reading is None, (
        "Poller muss surface_temp_c > plausibilitaet.max_temp_c verwerfen (E-40 Schicht 3)"
    )

    # Schicht 3b: Service bewertet None -> unknown, nie GRUEN (NF-01)
    result = assessment_service.assess_reading(None, now)
    assert result.risk_level is RiskLevel.UNKNOWN
    persisted = assessment_repo.get_latest()
    assert persisted is not None
    assert persisted.risk_level is RiskLevel.UNKNOWN


# ---------------------------------------------------------------------------
# Schicht 4 — DB-Ausfall (ADR E-40 §4, Fundstelle: main.py DTB-43)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "broken_repo",
    ["assessment_repo", "reading_repo"],
    ids=["assessment_repo_db_fehler", "reading_repo_db_fehler"],
)
def test_schicht4_db_ausfall_liefert_503(
    runtime: Runtime, broken_repo: str, client: TestClient
) -> None:
    """E-40 Schicht 4: RepositoryError bei einem der DB-Reads -> HTTP 503, nie GRUEN.

    Beweist fuer BEIDE DB-Lesepfade im Endpoint (assessment_repo.get_latest UND
    reading_repo.get_latest in GET /v1/assessment/current, gemeinsamer except-Block):
    GET /v1/assessment/current faengt RepositoryError contract-konform ab und
    antwortet mit 503 Error{code, message} — kein 500, kein {detail}-Feld, und
    niemals risk_level=green im Body (NF-01, E-40 Schicht 4, Contract-Format D).
    """
    # Genau das parametrisierte Repo durch einen Stub ersetzen, der RepositoryError wirft;
    # das jeweils andere bleibt das echte In-Memory-Double.
    broken_assessment_repo = (
        _AssessmentRepoDBFehler() if broken_repo == "assessment_repo" else runtime.assessment_repo
    )
    broken_reading_repo = (
        _ReadingRepoDBFehler() if broken_repo == "reading_repo" else runtime.reading_repo
    )
    if broken_repo == "reading_repo":
        # Defensive Isolierung des reading_repo-Pfads: eine gueltige Bewertung seeden, sodass
        # assessment_repo.get_latest() non-None liefert. So trifft dieser Fall eindeutig den
        # reading_repo-Fehlerzweig — auch falls main.py je einen frueheren assessment-None-Check
        # einzieht (sonst koennte der Fall still ueber den "keine Daten"-503 davonkommen).
        broken_assessment_repo.save(Assessment(ts=datetime.now(UTC), risk_level=RiskLevel.GREEN))
    # dataclasses.replace kopiert ALLE Felder des echten Runtime und ueberschreibt nur die
    # zwei gebrochenen Repos. Bewusst KEIN vollstaendiges Runtime(...) nachbauen: das wuerde
    # bei jedem neuen Runtime-Pflichtfeld (z. B. threshold_set_repo/alarm_repo) brechen,
    # obwohl der Test damit nichts zu tun hat (robust gegen DI-Graph-Erweiterungen).
    broken_runtime = replace(
        runtime,
        reading_repo=broken_reading_repo,
        assessment_repo=broken_assessment_repo,
    )
    app.dependency_overrides[get_runtime] = lambda: broken_runtime

    response = client.get("/v1/assessment/current")

    # E-40 Schicht 4: DB-Ausfall -> 503 (nie GRUEN, nie 500, nie {detail})
    assert response.status_code == 503
    body = response.json()
    # Contract-Fehlerformat: {code, message} (Contract D, E-36)
    assert "message" in body, f"Contract-Format erwartet {{code, message}}, erhalten: {body}"
    assert "code" in body, f"Contract-Format erwartet {{code, message}}, erhalten: {body}"
    assert "detail" not in body, "FastAPI-Rohformat {{detail}} verletzt den Contract (E-36)"
    # Hauptinvariante: nie GRUEN bei Ausfall (NF-01). Bewusst `not in` statt
    # `body.get("risk_level") != "green"`: bei einem korrekten Error-Body {code, message}
    # ist der Key ABWESEND -> body.get(...) waere None und der !=-Vergleich trivial wahr
    # (er wuerde sogar eine Regression durchlassen, die faelschlich 200+risk_level liefert).
    # Der Error-Response darf gar kein risk_level-Feld tragen.
    assert "risk_level" not in body, (
        f"Error-Response darf kein risk_level-Feld tragen (Contract D), erhalten: {body}"
    )


# ---------------------------------------------------------------------------
# Schicht 5 — Assessment-Kaskade (ADR E-40 §5, E-34, Fundstelle: core.assess_ice_risk)
# ---------------------------------------------------------------------------


def test_schicht5_kaskade_fehlender_taupunkt_nie_gruen(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    assessment_service: AssessmentService,
    thresholds: Thresholds,
    sensor_id: str,
) -> None:
    """E-40 Schicht 5: dew_point_c=None bei T_s <= Gefrierpunkt -> ORANGE, nie GRUEN (E-34).

    Beweist: fehlt der Taupunkt T_d (dew_point_c=None), nimmt assess_ice_risk
    konservativ Feuchte=wahr an (E-34). Bei T_s <= t_s_gefrierpunkt_c ergibt
    das genau ORANGE — die Schicht 5 bleibt in der regulaeren Ampel (kein
    unknown), liefert aber explizit NIE GRUEN (NF-01). Das unterscheidet sie
    von den Schichten 1-4 (die unknown liefern).

    Warum ORANGE und NICHT ROT: der ROT-Zweig in core.assess_ice_risk verlangt
    `delta_t is not None` (Z. 66). Bei dew_point_c=None ist delta_t=None -> ROT
    ist strukturell ausgeschlossen; der ORANGE-Zweig (T_s <= Gefrierpunkt UND
    humid) greift. Die Erwartung ist daher exakt ORANGE, nicht "ORANGE oder ROT".
    """
    now = datetime.now(UTC)
    freezing = thresholds.vereisung.t_s_gefrierpunkt_c

    # T_s gerade unter Gefrierpunkt; dew_point_c fehlt (z. B. RH unberechenbar
    # oder Sensor-Rohdaten zu stark gestört fuer die Magnus-Formel).
    reading = Reading(
        sensor_id=sensor_id,
        measured_at=now,
        surface_temp_c=freezing - 0.1,  # gerade unter Gefrierpunkt
        air_temp_c=2.0,
        humidity_pct=80.0,
        received_at=now,
        dew_point_c=None,  # Taupunkt nicht berechenbar -> Feuchte=wahr (konservativ, E-34)
        status=SensorStatus.OK,
    )
    reading_mit_id = _save_and_get_reading(reading_repo, reading)

    result = assessment_service.assess_reading(reading_mit_id, now)

    # E-40 Schicht 5 (E-34): Kaskade -> genau ORANGE, nie GRUEN, nie unknown
    assert result.risk_level is not RiskLevel.GREEN, (
        "Schicht 5: fehlender Taupunkt bei T_s <= Gefrierpunkt darf NIE GRUEN ergeben (NF-01)"
    )
    assert result.risk_level is not RiskLevel.UNKNOWN, (
        "Schicht 5 (Kaskade) bleibt in der regulaeren Ampel — unknown gehoert zu Schichten 1-4"
    )
    # ROT ist bei dew_point_c=None strukturell ausgeschlossen (core.py Z. 66: ROT verlangt
    # delta_t is not None) -> exakt ORANGE erwarten (nicht "ORANGE oder ROT").
    assert result.risk_level is RiskLevel.ORANGE, (
        f"Erwartet exakt ORANGE bei T_s <= Gefrierpunkt + dew_point=None (ROT ausgeschlossen, "
        f"delta_t=None), erhalten: {result.risk_level}"
    )
    persisted = assessment_repo.get_latest()
    assert persisted is not None
    # Persistenz-Assertion exakt wie die Rueckgabe (ORANGE), nicht nur "nicht GRUEN":
    # faengt eine Regression, die korrekt ORANGE zurueckgibt, aber falsch persistiert
    # (Konsistenz mit Schichten 1-4, die persistent denselben Wert wie result pruefen).
    assert persisted.risk_level is RiskLevel.ORANGE


# ---------------------------------------------------------------------------
# Schicht 6 — Serve-Zeit-Re-Check (ADR E-40 §6, Fundstelle: service.build_assessment_current)
# ---------------------------------------------------------------------------


def test_schicht6_serve_zeit_recheck_gruen_wird_unknown(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    assessment_service: AssessmentService,
    thresholds: Thresholds,
    sensor_id: str,
) -> None:
    """E-40 Schicht 6: persistiertes GRUEN altert zur Serve-Zeit -> unknown, nie GRUEN (NF-01).

    Beweist: build_assessment_current prueft die Aktualitaet des Readings NOCHMAL
    zum Abfragezeitpunkt (DTB-43, DTB-64). Ein vor stale_timeout gespeichertes
    GRUEN-Assessment wird bei spaeterem Abruf zu unknown — der Serve-Zeit-Re-Check
    verhindert, dass ein gecachtes GRUEN ausgeliefert wird (NF-01, E-40 Schicht 6).

    Unterschied zu Schicht 1: Schicht 1 prueft Stale zur ASSESS-Zeit (kein GRUEN
    landet im Repo). Schicht 6 prueft Stale zur SERVE-Zeit — das Repo enthaelt
    ein echtes GRUEN, das der Re-Check zur Auslieferungszeit ueberstimmt.
    """
    now = datetime.now(UTC)
    stale_timeout_s = thresholds.datenqualitaet.stale_timeout_s

    # 1. Bewertung: frisches Reading -> GRUEN wird persistiert.
    reading = _gruen_kandidat(sensor_id, now, thresholds)
    reading_mit_id = _save_and_get_reading(reading_repo, reading)
    assessment = assessment_service.assess_reading(reading_mit_id, now)
    assert assessment.risk_level is RiskLevel.GREEN, (
        "Schicht-6-Vorbedingung: Assessment muss GRUEN sein, damit der Serve-Zeit-Re-Check "
        "etwas zu ueberstimmen hat (prüfe _gruen_kandidat und Thresholds)"
    )

    # 2. Serve-Zeit: Reading ist laengst veraltet (> stale_timeout nach der Bewertung).
    serve_now = now + timedelta(seconds=stale_timeout_s + 60)

    response = build_assessment_current(assessment, reading_mit_id, serve_now, stale_timeout_s)

    # E-40 Schicht 6: Serve-Zeit-Re-Check -> unknown, nie GRUEN (NF-01)
    assert response.risk_level is RiskLevel.UNKNOWN, (
        "Schicht 6: persistiertes GRUEN muss zur Serve-Zeit zu unknown werden (NF-01, E-40 §6)"
    )
    assert response.is_stale is True
    # Contract (E-36): measured_at ist Pflichtfeld und MUSS auch im Fail-safe gesetzt sein
    # (auf 200 immer vorhanden) — es traegt die G1-Messzeit des ausloesenden Readings.
    assert response.measured_at == reading_mit_id.measured_at
    # sensor_status bleibt OK: hier loest nur Stale (Serve-Zeit) den Fail-safe aus, kein fault.
    assert response.sensor_status is SensorStatus.OK
    # Contract (E-36): Messwerte werden bei Fail-safe genullt
    assert response.surface_temp_c is None
    assert response.dew_point_c is None
    assert response.delta_t is None
    assert response.humidity_pct is None
    # Hinweis (Review-Frage air_temp_c): AssessmentCurrent fuehrt BEWUSST kein air_temp_c —
    # die Lufttemperatur ist nur G1-Eingangsgroesse fuer die Taupunkt-Berechnung, nicht Teil
    # des G2->G3-Wire (Contract §2a). Es gibt daher nichts zu nullen (kein Feld vorhanden).
