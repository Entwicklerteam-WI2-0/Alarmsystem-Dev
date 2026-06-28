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

Mehrwert:
  - Alle sechs E-40-Schichten sind explizit benannt und maschinell geprueft.
  - Schicht 3 testet den Poller-Validierungspfad (_build_reading ohne HTTP-Layer).
  - Schicht 4 ist ein neuer Fall: DB-Ausfall -> 503 (bisher kein dedizierter Test).
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

from datetime import UTC, datetime, timedelta

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

_CLIENT = TestClient(app)


# ---------------------------------------------------------------------------
# Stub fuer DB-Ausfall-Simulation (Schicht 4, E-40)
# ---------------------------------------------------------------------------


class _AssessmentRepoDBFehler(InMemoryAssessmentRepository):
    """In-Memory-Stub, dessen get_latest immer RepositoryError wirft.

    Simuliert einen DB-Ausfall (Verbindungsabbruch / OperationalError) an genau
    der Stelle, die GET /v1/assessment/current zuerst aufruft (E-40 Schicht 4).
    save() bleibt intakt, damit der Service unbehelligt schreibt (falls noetig).
    """

    def get_latest(self) -> Assessment | None:  # type: ignore[override]
        raise RepositoryError("Test-Stub: DB ausgefallen (Schicht 4, E-40)")


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


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
def _cleanup_app_state() -> None:  # type: ignore[return]
    """Setzt app.dependency_overrides und app.state nach jedem Test zurueck.

    Notwendig fuer die API-Tests (Schicht 4), damit ein ueberschriebener
    Runtime nicht in den naechsten Test leckt. Bei Service-level-Tests
    ist dieser Cleanup eine No-Op.
    """
    try:
        yield  # type: ignore[misc]
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
    """E-40 Schicht 2: reading.status=fault -> AssessmentService -> unknown, nie GRUEN (NF-01).

    Belegt: der Sensor-Fault-Pfad in AssessmentService (service.py) greift VOR
    der regulaeren Kaskade. Messwerte koennen GRUEN anzeigen — fault ueberstimmt
    sie (NF-01). Das ausloesende Reading wird verknuepft (NF-05).
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

    Beweist zwei Real-Pfad-Stufen ohne HTTP-Schicht (G1-HTTP ist G1-external):
    a) Poller._build_reading verwirft surface_temp_c > plausibilitaet.max_temp_c -> None.
    b) AssessmentService.assess_reading(reading=None) -> unknown (NF-01).
    Die Plausibilitaetsgrenzen kommen aus config/thresholds.json (NF-05, kein Hardcode).
    """
    now = datetime.now(UTC)
    max_temp = thresholds.plausibilitaet.max_temp_c

    # G1-Payload mit surface_temp_c klar ausserhalb der Obergrenze.
    payload: dict = {
        "sensor_id": sensor_id,
        "measured_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "surface_temp_c": max_temp + 10.0,  # klar jenseits der Plausibilitaetsgrenze
        "air_temp_c": 5.0,
        "humidity_pct": 80.0,
        "status": "ok",
    }

    # Schicht 3a: Poller-Plausibilitaetspruefung verwirft -> None (keine Persistenz)
    reading = poller._build_reading(payload)
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


def test_schicht4_db_ausfall_liefert_503(runtime: Runtime) -> None:
    """E-40 Schicht 4: RepositoryError bei assessment_repo.get_latest -> HTTP 503, nie GRUEN.

    Beweist: GET /v1/assessment/current faengt RepositoryError contract-konform ab
    und antwortet mit 503 Error{code, message} — kein 500, kein {detail}-Feld,
    und niemals risk_level=green im Body (NF-01, E-40 Schicht 4, Contract-Format D).
    """
    broken_runtime = Runtime(
        thresholds=runtime.thresholds,
        reading_repo=runtime.reading_repo,
        # Nur assessment_repo wird gebrochen — erster get_latest-Aufruf im Endpoint.
        assessment_repo=_AssessmentRepoDBFehler(),
        audit_repo=runtime.audit_repo,
        poller=runtime.poller,
        service=runtime.service,
        alarm_generator=runtime.alarm_generator,
        alarm_broadcaster=runtime.alarm_broadcaster,
    )
    app.dependency_overrides[get_runtime] = lambda: broken_runtime

    response = _CLIENT.get("/v1/assessment/current")

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
    assert persisted.risk_level is not RiskLevel.GREEN


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
