"""Tests fuer die Assessment-Orchestrierung (DTB-64).

Belegt das **NF-01-Enforcement zur Laufzeit** an beiden Stellen:
- Assess-Zeit (AssessmentService.assess_reading): keine/stale/fault Daten -> unknown,
  nie GRUEN; sonst regulaere Bewertung; Persistenz + Audit verdrahtet.
- Serve-Zeit (build_assessment_current): stale/fault zum Abfragezeitpunkt -> unknown
  + Messwerte genullt; Contract-konformer Wire-Response.

Alle Schwellen aus der Default-Config (DTB-15), keine Hardcodes.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.assessment.service import AssessmentService, build_assessment_current
from src.config.loader import load_thresholds
from src.model.enums import AuditEventType, RiskLevel, SensorStatus
from src.model.schemas import Assessment, Reading
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository
from src.storage.repository import RepositoryError


@pytest.fixture
def thresholds():
    return load_thresholds()


def _reading(
    measured_at: datetime,
    *,
    surface: float = 2.0,
    dew: float | None = 0.0,
    status: SensorStatus = SensorStatus.OK,
    rid: int | None = 1,
) -> Reading:
    """Baut ein Reading; received_at = measured_at (fuer den Test irrelevant).

    `rid` ist defaultmaessig gesetzt (= vom Poller persistiert, DTB-28-Invariante);
    `rid=None` modelliert ein noch nicht persistiertes Reading.
    """
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


def _make_service(thresholds) -> AssessmentService:
    """Service mit frischen In-Memory-Repos (fuer Tests ohne Repo-Inspektion)."""
    return AssessmentService(thresholds, InMemoryAssessmentRepository(), InMemoryAuditRepository())


# ---------------------------------------------------------------------------
# AssessmentService.assess_reading — Assess-Zeit-NF-01 + Persistenz + Audit
# ---------------------------------------------------------------------------


def test_forecast_loest_gelb_aus_und_wird_persistiert(thresholds):
    # DTB-33 / FA-06: T_s=2.0 + trocken -> ohne Prognose GRUEN; Prognose -1.0 (<= 0)
    # -> GELB-Vorwarnung. Der Prognosewert muss im Snapshot persistiert werden (FA-05).
    arepo, audit = InMemoryAssessmentRepository(), InMemoryAuditRepository()
    service = AssessmentService(thresholds, arepo, audit)
    now = datetime.now(UTC)

    result = service.assess_reading(
        _reading(now, surface=2.0, dew=0.0), now, forecast_surface_temp_c=-1.0
    )

    assert result.risk_level is RiskLevel.YELLOW
    assert result.forecast_surface_temp_c == pytest.approx(-1.0)
    persisted = arepo.get_latest()
    assert persisted is not None
    assert persisted.forecast_surface_temp_c == pytest.approx(-1.0)


def test_ohne_forecast_bleibt_gruen_und_feld_none(thresholds):
    # Default (kein forecast) haelt das bestehende Verhalten: GRUEN, Feld None.
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(_reading(now, surface=2.0, dew=0.0), now)

    assert result.risk_level is RiskLevel.GREEN
    assert result.forecast_surface_temp_c is None


def test_healthy_reading_is_assessed_persisted_and_audited(thresholds):
    # Arrange
    arepo, audit = InMemoryAssessmentRepository(), InMemoryAuditRepository()
    service = AssessmentService(thresholds, arepo, audit)
    now = datetime.now(UTC)

    # Act — T_s=2.0 (>1.0), Taupunkt 0 -> trocken -> GRUEN
    result = service.assess_reading(_reading(now, surface=2.0, dew=0.0), now)

    # Assert
    assert result.risk_level == RiskLevel.GREEN
    assert result.id == 1
    assert arepo.get_latest() is not None
    assert arepo.get_latest().id == 1
    assert len(audit.all()) == 1
    assert audit.all()[0].event_type == AuditEventType.ASSESSMENT_MADE


def test_negative_delta_t_assesses_ice_risk_not_green(thresholds):
    # Arrange — Taupunkt (1.0) UEBER Oberflaechentemp (-0.5): delta_t = -1.5
    # (T_d > T_s) ist ein klares Eisrisiko und muss sicherheitskritisch bewertet
    # werden, nicht GRUEN. Deckt den Service-Pfad fuer einen nicht-gruenen,
    # persistierten Risk-Level ab (assess_ice_risk-Kern, Schwellenwerte.md §2:
    # T_s<=Gefrierpunkt UND delta_t<=Kondensation -> ROT).
    arepo, audit = InMemoryAssessmentRepository(), InMemoryAuditRepository()
    service = AssessmentService(thresholds, arepo, audit)
    now = datetime.now(UTC)

    # Act — T_s=-0.5 (<=Gefrierpunkt 0.0) UND delta_t=-1.5 (<=Kondensation 0.0) -> ROT
    result = service.assess_reading(_reading(now, surface=-0.5, dew=1.0), now)

    # Assert — hoechste Risikostufe ROT, korrekt persistiert + auditiert; nie GRUEN.
    assert result.risk_level == RiskLevel.RED
    assert result.risk_level != RiskLevel.GREEN
    assert result.delta_t == pytest.approx(-1.5)
    assert result.id == 1
    assert arepo.get_latest().id == 1
    assert len(audit.all()) == 1
    assert audit.all()[0].event_type == AuditEventType.ASSESSMENT_MADE


def test_none_reading_is_unknown(thresholds):
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(None, now)

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id is None  # ohne Reading kein Bezug moeglich


def test_fault_reading_is_unknown_never_green(thresholds):
    # Arrange — Werte, die fresh GRUEN ergaeben; fault muss sie ueberstimmen.
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(
        _reading(now, surface=20.0, dew=0.0, status=SensorStatus.FAULT), now
    )

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id == 1  # ausloesendes Reading verknuepft (Traceability)


def test_stale_reading_is_unknown_never_green(thresholds):
    # Arrange — warmes (waere GRUEN) aber veraltetes Reading.
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)

    result = service.assess_reading(_reading(old, surface=20.0, dew=0.0), now)

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id == 1  # ausloesendes Reading verknuepft (Traceability)


def test_naive_now_raises(thresholds):
    service = _make_service(thresholds)

    with pytest.raises(ValueError, match="zeitzonenbewusst"):
        service.assess_reading(None, datetime.now())  # noqa: DTZ005 - bewusst naiv


def test_good_path_requires_persisted_reading_id(thresholds):
    # Arrange — gesundes Reading (waere GRUEN), aber noch nicht persistiert (id=None).
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    # Act + Assert — die DTB-28-Invariante muss laut scheitern, statt einen Snapshot
    # mit reading_id=NULL zu schreiben und so die Audit-Traceability (NF-05) zu brechen.
    with pytest.raises(ValueError, match="Poller muss das Reading"):
        service.assess_reading(_reading(now, surface=2.0, dew=0.0, rid=None), now)


class _ThrowingAuditRepository(InMemoryAuditRepository):
    """Audit-Double, das bei jedem append wirft (best-effort-Garantie testen)."""

    def append(self, entry):  # noqa: ARG002 - Signatur des Interface, Wert ungenutzt
        raise RepositoryError("Audit-Backend nicht verfuegbar")


def test_audit_failure_does_not_break_cycle(thresholds):
    # Arrange — Audit wirft IMMER; der Bewertungszyklus muss trotzdem durchlaufen
    # (NF-01 vor NF-09: ein Audit-Fehler darf den Sicherheits-Output nie blockieren).
    arepo = InMemoryAssessmentRepository()
    service = AssessmentService(thresholds, arepo, _ThrowingAuditRepository())
    now = datetime.now(UTC)

    # Act — gesunder Wert (waere GRUEN); kein raise trotz Audit-Fehler erwartet.
    result = service.assess_reading(_reading(now, surface=2.0, dew=0.0), now)

    # Assert — Bewertung wurde erzeugt UND persistiert, obwohl das Audit scheiterte.
    assert result.id == 1
    assert result.risk_level == RiskLevel.GREEN
    assert arepo.get_latest() is not None


# ---------------------------------------------------------------------------
# build_assessment_current — Serve-Zeit-NF-01 (Wire-Response)
# ---------------------------------------------------------------------------


def test_current_fresh_ok_keeps_assessment(thresholds):
    now = datetime.now(UTC)
    reading = _reading(now, surface=2.0, dew=0.0)
    assessment = Assessment(
        ts=now,
        risk_level=RiskLevel.GREEN,
        surface_temp_c=2.0,
        dew_point_c=0.0,
        delta_t=2.0,
        humidity_pct=80.0,
    )

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level == RiskLevel.GREEN
    assert cur.is_stale is False
    assert cur.sensor_status == SensorStatus.OK
    assert cur.surface_temp_c == 2.0
    assert cur.measured_at == reading.measured_at
    assert cur.assessed_at == assessment.ts


def test_current_stale_forces_unknown_and_nulls_measurements(thresholds):
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)
    reading = _reading(old, surface=2.0, dew=0.0)
    assessment = Assessment(ts=old, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level == RiskLevel.UNKNOWN
    assert cur.is_stale is True
    assert cur.surface_temp_c is None
    assert cur.dew_point_c is None


def test_current_fault_forces_unknown(thresholds):
    now = datetime.now(UTC)
    reading = _reading(now, status=SensorStatus.FAULT)
    assessment = Assessment(ts=now, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level == RiskLevel.UNKNOWN
    assert cur.sensor_status == SensorStatus.FAULT
    assert cur.is_stale is False


def test_current_stale_and_fault_names_both_reasons(thresholds):
    # Arrange — Reading ist gleichzeitig stale UND fault (kombinierter Fail-safe-Pfad).
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)
    reading = _reading(old, status=SensorStatus.FAULT)
    assessment = Assessment(ts=old, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    # Beide Gruende erscheinen in explanation; Invariante bleibt unknown (nie GRUEN).
    assert cur.risk_level == RiskLevel.UNKNOWN
    assert cur.is_stale is True
    assert cur.sensor_status == SensorStatus.FAULT
    assert cur.explanation == "Fail-safe: stale + sensor fault"


def test_current_none_reading_raises(thresholds):
    # Vertrag: der No-Data-Fall gehoert vom Aufrufer (DTB-43) mit 503 abgefangen,
    # nicht hierher — der Guard muss laut scheitern statt einen AttributeError zu werfen.
    assessment = Assessment(ts=datetime.now(UTC), risk_level=RiskLevel.GREEN)

    with pytest.raises(ValueError, match="reading darf nicht None sein"):
        build_assessment_current(
            assessment, None, datetime.now(UTC), thresholds.datenqualitaet.stale_timeout_s
        )


# ---------------------------------------------------------------------------
# DTB-66: driving_factor + explanation je Risikostufe (Assess-Zeit)
# ---------------------------------------------------------------------------


def test_rot_setzt_dew_point_als_driving_factor(thresholds):
    """ROT: Kondensation -> treibender Faktor ist der Taupunkt-Abstand (ΔT ≤ 0)."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    # T_s=-0.5 ≤ Gefrierpunkt, T_d=1.0 -> ΔT=-1.5 ≤ 0 (Kondensation) -> ROT
    result = service.assess_reading(_reading(now, surface=-0.5, dew=1.0), now)

    assert result.risk_level is RiskLevel.RED
    assert result.driving_factor == "dew_point"
    assert result.explanation is not None
    assert len(result.explanation) <= 512
    # Muss auf Eisbildung/Kondensation hinweisen
    assert "Eisbildung" in result.explanation or "Kondensation" in result.explanation


def test_orange_mit_taupunkt_setzt_dew_point_als_driving_factor(thresholds):
    """ORANGE mit bekanntem T_d: Feuchte vorhanden -> driving_factor dew_point."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    # T_s=-1.0, T_d=-1.5 -> ΔT=0.5 (≤1.0, Feuchte vorhanden, >0 -> nicht Kondensation) -> ORANGE
    result = service.assess_reading(_reading(now, surface=-1.0, dew=-1.5), now)

    assert result.risk_level is RiskLevel.ORANGE
    assert result.driving_factor == "dew_point"
    assert result.explanation is not None
    assert len(result.explanation) <= 512
    assert "Feuchte" in result.explanation or "Vereisung" in result.explanation


def test_orange_ohne_taupunkt_setzt_surface_temp_als_driving_factor(thresholds):
    """ORANGE bei fehlendem T_d: Fail-safe Feuchte=wahr, Faktor ist surface_temp."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    # T_s=-1.0 ≤ Gefrierpunkt, T_d=None -> Feuchte=konservativ-wahr -> ORANGE
    result = service.assess_reading(_reading(now, surface=-1.0, dew=None), now)

    assert result.risk_level is RiskLevel.ORANGE
    assert result.driving_factor == "surface_temp"
    assert result.explanation is not None
    assert len(result.explanation) <= 512
    # Muss auf fehlenden Taupunkt/Fail-safe hinweisen
    assert "Taupunkt" in result.explanation or "Fail-safe" in result.explanation


def test_gelb_durch_oberflaeche_setzt_surface_temp_als_driving_factor(thresholds):
    """GELB durch Auffang (T_s kalt/grenzwertig): driving_factor = surface_temp."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    # T_s=0.5 ≤ 1.0 (GELB-Auffang), ΔT=5.5 (trocken, keine Feuchte) -> GELB
    result = service.assess_reading(_reading(now, surface=0.5, dew=-5.0), now)

    assert result.risk_level is RiskLevel.YELLOW
    assert result.driving_factor == "surface_temp"
    assert result.explanation is not None
    assert len(result.explanation) <= 512
    assert "grenzwertig" in result.explanation.lower() or "kalt" in result.explanation.lower()


def test_gelb_durch_fehlenden_taupunkt_bei_warmer_oberflaeche(thresholds):
    """GELB Fail-safe: T_s warm (>Auffang), keine Prognose, T_d unbestimmbar -> nie GRUEN."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    # T_s=2.0 (>1.0 Auffang), dew=None -> Fail-safe nie GRUEN -> GELB; driving_factor dew_point
    result = service.assess_reading(_reading(now, surface=2.0, dew=None), now)

    assert result.risk_level is RiskLevel.YELLOW
    assert result.driving_factor == "dew_point"
    assert result.explanation is not None
    assert "Taupunkt" in result.explanation


def test_gelb_durch_prognose_setzt_forecast_als_driving_factor(thresholds):
    """GELB durch 30-min-Prognose (nicht durch aktuellen T_s): driving_factor = forecast."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    # T_s=2.0 (> 1.0, waere GRUEN), Prognose=-1.0 (≤ 0) -> GELB durch Prognose
    result = service.assess_reading(
        _reading(now, surface=2.0, dew=0.0), now, forecast_surface_temp_c=-1.0
    )

    assert result.risk_level is RiskLevel.YELLOW
    assert result.driving_factor == "forecast"
    assert result.explanation is not None
    assert len(result.explanation) <= 512
    assert "Prognose" in result.explanation or "forecast" in result.explanation.lower()


def test_gelb_durch_defekte_prognose_leakt_kein_nan(thresholds):
    """GELB durch defekte (NaN) Prognose: explanation darf kein 'nan' leaken (DTB-66 Review)."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    # T_s=2.0 (waere GRUEN), Prognose=NaN -> defektes Forecasting -> konservativ GELB
    result = service.assess_reading(
        _reading(now, surface=2.0, dew=0.0), now, forecast_surface_temp_c=float("nan")
    )

    assert result.risk_level is RiskLevel.YELLOW
    assert result.driving_factor == "forecast"
    assert result.explanation is not None
    assert "nan" not in result.explanation.lower()
    assert "defekt" in result.explanation.lower() or "Prognosedaten" in result.explanation


def test_gelb_warme_oberflaeche_harmlose_prognose_ist_dew_point_nicht_forecast(thresholds):
    """GELB via T_d-Fail-safe (dew=None), Prognose UEBER Schwelle -> kein forecast-Text.

    Regression DTB-66 Review HIGH: derive_explanation darf den forecast-Zweig nur
    waehlen, wenn die Prognose tatsaechlich Gefrieren droht (<= t_s_grenz_c). Bei
    surface=2.0, dew=None, forecast=5.0 gibt assess_ice_risk GELB ueber den
    dew=None-Fail-safe -> driving_factor muss dew_point sein, nicht forecast, und der
    Text darf nicht widerspruechlich "5.0 °C ≤ 0.0 °C" behaupten.
    """
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(
        _reading(now, surface=2.0, dew=None), now, forecast_surface_temp_c=5.0
    )

    assert result.risk_level is RiskLevel.YELLOW
    assert result.driving_factor == "dew_point"
    assert result.explanation is not None
    assert "Taupunkt" in result.explanation
    assert "Prognose" not in result.explanation


def test_happy_pfad_nan_surface_ist_unknown_mit_sensor_data_faktor(thresholds):
    """NaN-Sensorwert im Happy-Pfad -> UNKNOWN mit driving_factor=sensor_data.

    DTB-66 Review MEDIUM: assess_ice_risk gibt bei NaN/inf UNKNOWN; der Wire-Response
    soll dann nicht ohne driving_factor/explanation dastehen (Observability, NF-01-Geist).
    """
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(_reading(now, surface=float("nan"), dew=0.0), now)

    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.driving_factor == "sensor_data"
    assert result.explanation is not None
    assert len(result.driving_factor) <= 64
    assert len(result.explanation) <= 512
    assert "ungültig" in result.explanation or "NaN" in result.explanation


def test_happy_pfad_inf_surface_ist_unknown_mit_sensor_data_faktor(thresholds):
    """inf-Sensorwert im Happy-Pfad -> UNKNOWN mit driving_factor=sensor_data.

    Pendant zum NaN-Test (DTB-66 Review INFO): math.isfinite faengt ebenfalls inf
    ab, daher liefert assess_ice_risk UNKNOWN. Dieser Test schliesst die Coverage
    ohne Mehraufwand ab und sichert den Pfad gegen eine Veraenderung der
    Endlichkeits-Pruefung.
    """
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(_reading(now, surface=float("inf"), dew=0.0), now)

    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.driving_factor == "sensor_data"
    assert result.explanation is not None
    assert len(result.driving_factor) <= 64
    assert len(result.explanation) <= 512
    assert "ungültig" in result.explanation
    """GRUEN: kein Risiko, driving_factor und explanation bleiben None."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    # T_s=2.0 (>1.0), ΔT=2.0 (trocken) -> GRUEN
    result = service.assess_reading(_reading(now, surface=2.0, dew=0.0), now)

    assert result.risk_level is RiskLevel.GREEN
    assert result.driving_factor is None
    assert result.explanation is None


def test_stale_reading_setzt_stale_als_driving_factor(thresholds):
    """Stale Reading -> unknown; driving_factor='stale'."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)

    result = service.assess_reading(_reading(old, surface=20.0, dew=0.0), now)

    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.driving_factor == "stale"
    assert result.explanation is not None
    assert len(result.explanation) <= 512
    # Inhalts-Assert: explanation nennt den Fail-safe-Grund (DTB-66 Review LOW).
    assert "stale" in result.explanation.lower() or "veraltet" in result.explanation.lower()
    assert "Fail-safe" in result.explanation


def test_fault_reading_setzt_sensor_fault_als_driving_factor(thresholds):
    """Sensor-Fault -> unknown; driving_factor='sensor_fault'."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(
        _reading(now, surface=20.0, dew=0.0, status=SensorStatus.FAULT), now
    )

    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.driving_factor == "sensor_fault"
    assert result.explanation is not None
    assert len(result.explanation) <= 512
    # Inhalts-Assert: explanation nennt den Fail-safe-Grund (DTB-66 Review LOW).
    assert "fault" in result.explanation.lower()
    assert "Fail-safe" in result.explanation


def test_kein_reading_setzt_stale_als_driving_factor(thresholds):
    """Kein Reading (None) -> unknown; driving_factor='stale' (keine Daten verfuegbar)."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    result = service.assess_reading(None, now)

    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.driving_factor == "stale"
    assert result.explanation is not None
    assert len(result.explanation) <= 512
    # Inhalts-Assert: explanation nennt den Fail-safe-Grund (DTB-66 Review LOW).
    assert "keine" in result.explanation.lower() or "daten" in result.explanation.lower()
    assert "Fail-safe" in result.explanation


# ---------------------------------------------------------------------------
# DTB-66: driving_factor in build_assessment_current (Serve-Zeit)
# ---------------------------------------------------------------------------


def test_build_current_stale_setzt_stale_driving_factor(thresholds):
    """Serve-Zeit-Stale -> driving_factor='stale'."""
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)
    reading = _reading(old, surface=2.0, dew=0.0)
    assessment = Assessment(ts=old, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level is RiskLevel.UNKNOWN
    assert cur.driving_factor == "stale"


def test_build_current_fault_setzt_sensor_fault_driving_factor(thresholds):
    """Serve-Zeit-Fault -> driving_factor='sensor_fault'."""
    now = datetime.now(UTC)
    reading = _reading(now, status=SensorStatus.FAULT)
    assessment = Assessment(ts=now, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level is RiskLevel.UNKNOWN
    assert cur.driving_factor == "sensor_fault"


def test_build_current_stale_und_fault_setzt_sensor_fault_driving_factor(thresholds):
    """Stale + Fault gleichzeitig -> driving_factor='sensor_fault' (gravierender)."""
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)
    reading = _reading(old, status=SensorStatus.FAULT)
    assessment = Assessment(ts=old, risk_level=RiskLevel.GREEN, surface_temp_c=2.0)

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level is RiskLevel.UNKNOWN
    assert cur.driving_factor == "sensor_fault"


def test_build_current_ok_reicht_assessment_driving_factor_durch(thresholds):
    """Frischer/ok Response: driving_factor und explanation aus der gespeicherten Bewertung."""
    now = datetime.now(UTC)
    reading = _reading(now, surface=2.0, dew=0.0)
    assessment = Assessment(
        ts=now,
        risk_level=RiskLevel.GREEN,
        surface_temp_c=2.0,
        dew_point_c=0.0,
        delta_t=2.0,
        humidity_pct=80.0,
        driving_factor=None,
        explanation=None,
    )

    cur = build_assessment_current(
        assessment, reading, now, thresholds.datenqualitaet.stale_timeout_s
    )

    assert cur.risk_level is RiskLevel.GREEN
    assert cur.driving_factor is None
    assert cur.explanation is None


def test_driving_factor_laenge_max_64(thresholds):
    """driving_factor darf maximal 64 Zeichen lang sein (Wire-Contract maxLength)."""
    service = _make_service(thresholds)
    now = datetime.now(UTC)

    for surface, dew, forecast in [
        (-0.5, 1.0, None),  # ROT
        (-1.0, -1.5, None),  # ORANGE
        (0.5, -5.0, None),  # GELB surface
        (2.0, 0.0, -1.0),  # GELB forecast
    ]:
        result = service.assess_reading(
            _reading(now, surface=surface, dew=dew), now, forecast_surface_temp_c=forecast
        )
        if result.driving_factor is not None:
            assert len(result.driving_factor) <= 64, (
                f"driving_factor '{result.driving_factor}' ueberschreitet 64 Zeichen"
            )
        if result.explanation is not None:
            assert len(result.explanation) <= 512, (
                f"explanation '{result.explanation}' ueberschreitet 512 Zeichen"
            )
