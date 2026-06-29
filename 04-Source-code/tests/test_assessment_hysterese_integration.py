"""Tests fuer die RiskHysterese-Einbindung in den AssessmentService (DTB-27).

Prueft die Korrektheit der Verdrahtung — nicht die Hysterese-Logik selbst
(die in test_riskhysterese.py abgedeckt ist), sondern dass der Service die
Zustandsmaschine in JEDEM Poll-Zyklus korrekt tickt:

  * Recovery-nach-Stale (Blocker 1): ROT -> Stale (UNKNOWN) -> GRUEN-Recovery
    muss sofort GRUN zeigen, nicht auf ROT kleben bleiben.
  * Fail-safe-Pfade ticken die Hysterese (State-Desync-Schutz).
  * Serve-Pfad (build_assessment_current) liefert die entprellte Stufe.
  * Alarm-Generierung folgt weiterhin der rohen Stufe (Entkopplung).
  * driving_factor/explanation passen zur angezeigten Stufe (Blocker 2).
"""

from datetime import UTC, datetime, timedelta

from src.alarm.riskhysterese import RiskHysterese
from src.assessment.service import AssessmentService, build_assessment_current
from src.config.loader import load_thresholds
from src.model.enums import RiskLevel, SensorStatus
from src.model.schemas import Reading
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository

_THR = load_thresholds()
_T0 = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _reading(now, surface, dew, status=SensorStatus.OK, rid=1, measured_at=None):
    return Reading(
        id=rid,
        sensor_id="anr-rwy-01",
        measured_at=measured_at if measured_at is not None else now,
        surface_temp_c=surface,
        air_temp_c=3.0,
        humidity_pct=80.0,
        received_at=now,
        dew_point_c=dew,
        status=status,
    )


def _service() -> AssessmentService:
    return AssessmentService(
        _THR,
        RiskHysterese(_THR.hysterese),
        InMemoryAssessmentRepository(),
        InMemoryAuditRepository(),
    )


# ---------------------------------------------------------------------------
# Blocker 1: Recovery-nach-Stale (der Test, der den Bug aufdeckt)
# ---------------------------------------------------------------------------


def test_recovery_nach_stale_zeigt_sofort_gruen_nicht_gehaltenes_rot():
    """ROT -> Stale (UNKNOWN) -> GRUEN-Recovery zeigt sofort GRUEN.

    Ohne uebernimm_unknown wuerde _current auf ROT kleben bleiben und der GRUEN-Poll
    als Herabstufung ins Deadband+Stabilitaet-Fenster laufen (>= 5 min auf ROT).
    Spezifikation riskhysterese.py: Recovery aus UNKNOWN -> sofort.
    """
    service = _service()

    # Poll 1: ROT (T_s=-1, T_d=-1 -> delta_t=0 <= kondensation 0, gefroren)
    poll1 = _T0
    r1 = service.assess_reading(_reading(poll1, surface=-1.0, dew=-1.0), poll1)
    assert r1.risk_level is RiskLevel.RED
    assert r1.displayed_risk_level is RiskLevel.RED

    # Poll 2: STALE (measured_at zu alt -> is_stale greift -> Fail-safe UNKNOWN).
    # Wichtig: die Hysterese muss den UNKNOWN-Durchgang registrieren (tick).
    stale_measured = poll1 - timedelta(seconds=200)  # > 120 s stale_timeout
    poll2 = poll1 + timedelta(seconds=30)
    r2 = service.assess_reading(
        _reading(poll2, surface=-1.0, dew=-1.0, measured_at=stale_measured), poll2
    )
    assert r2.risk_level is RiskLevel.UNKNOWN
    assert r2.displayed_risk_level is RiskLevel.UNKNOWN

    # Poll 3: GRUEN-Recovery (T_s=2, T_d=0 -> trocken, > gelb_auffang).
    # Erwartung: sofort GRUEN (Recovery aus UNKNOWN), NICHT ROT gehalten.
    poll3 = poll2 + timedelta(seconds=30)
    r3 = service.assess_reading(_reading(poll3, surface=2.0, dew=0.0), poll3)
    assert r3.risk_level is RiskLevel.GREEN
    assert r3.displayed_risk_level is RiskLevel.GREEN, (
        "Recovery aus UNKNOWN muss sofort GRUEN zeigen — klebt die Ampel auf ROT, "
        "wurde die Hysterese im Stale-Poll nicht getickt (Blocker 1)."
    )


# ---------------------------------------------------------------------------
# Fail-safe-Pfade ticken die Hysterese
# ---------------------------------------------------------------------------


def test_failsafe_keine_daten_tickt_hysterese_auf_unknown():
    """reading=None (G1 nicht erreichbar) -> UNKNOWN, Hysterese-Zustand auf UNKNOWN."""
    service = _service()
    now = _T0

    result = service.assess_reading(None, now)

    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.displayed_risk_level is RiskLevel.UNKNOWN
    # Folge-Poll mit GRUEN recoveryt sofort (beweist, dass unknown registriert wurde)
    poll2 = now + timedelta(seconds=30)
    r2 = service.assess_reading(_reading(poll2, surface=2.0, dew=0.0), poll2)
    assert r2.displayed_risk_level is RiskLevel.GREEN


def test_failsafe_sensor_fault_tickt_hysterese_auf_unknown():
    """Sensor fault -> UNKNOWN, Hysterese-Zustand auf UNKNOWN."""
    service = _service()
    now = _T0

    result = service.assess_reading(
        _reading(now, surface=-1.0, dew=-1.0, status=SensorStatus.FAULT), now
    )

    assert result.risk_level is RiskLevel.UNKNOWN
    assert result.displayed_risk_level is RiskLevel.UNKNOWN


# ---------------------------------------------------------------------------
# Serve-Pfad: build_assessment_current liefert entprellte Stufe
# ---------------------------------------------------------------------------


def test_build_assessment_current_liefert_displayed_risk_level(thresholds):
    """Bei roh != displayed (Hysterese haelt) liefert der Wire die entprellte Stufe.

    Sequenz: erst ORANGE etablieren, dann Werte die roh GELB wuerden, aber im
    Deadband liegen -> displayed bleibt ORANGE gehalten. Serve zeigt ORANGE.
    """
    service = _service()

    # ORANGE etablieren: T_s=-1, T_d=-1.5 -> delta_t=0.5 (feucht, > kondensation 0)
    poll1 = _T0
    service.assess_reading(_reading(poll1, surface=-1.0, dew=-1.5), poll1)

    # Werte die roh GELB sind, aber im Deadband (verschobene Schwelle haelt ORANGE):
    # roh GELB verlangt T_s > gefrierpunkt(0); streng(0+0.5) verlangt T_s > 0.5.
    # T_s=0.3 -> roh GELB (0 < 0.3 <= 1), streng ORANGE (0.3 <= 0.5) -> ORANGE gehalten.
    poll2 = _T0 + timedelta(seconds=10)
    assessment = service.assess_reading(_reading(poll2, surface=0.3, dew=-1.5), poll2)

    assert assessment.risk_level is RiskLevel.YELLOW  # roh
    assert assessment.displayed_risk_level is RiskLevel.ORANGE  # gehalten

    # Serve: Ampel zeigt ORANGE (entprellt), nicht GELB (roh)
    served = build_assessment_current(
        assessment,
        _reading(poll2, surface=0.3, dew=-1.5),
        poll2,
        thresholds.datenqualitaet.stale_timeout_s,
    )
    assert served.risk_level is RiskLevel.ORANGE


def test_build_assessment_current_fallback_auf_risk_level_bei_displayed_none(thresholds):
    """Legacy-Assessment ohne displayed_risk_level -> Serve faellt auf risk_level zurueck."""
    now = _T0
    from src.model.schemas import Assessment

    legacy = Assessment(
        ts=now,
        reading_id=1,
        risk_level=RiskLevel.YELLOW,
        driving_factor=None,
        explanation=None,
        surface_temp_c=0.5,
        dew_point_c=-5.0,
        delta_t=5.5,
        humidity_pct=80.0,
        displayed_risk_level=None,  # Legacy
    )
    served = build_assessment_current(
        legacy,
        _reading(now, surface=0.5, dew=-5.0),
        now,
        thresholds.datenqualitaet.stale_timeout_s,
    )
    assert served.risk_level is RiskLevel.YELLOW


# ---------------------------------------------------------------------------
# Blocker 2: driving_factor/explanation passen zur angezeigten Stufe
# ---------------------------------------------------------------------------


def test_explanation_erklaert_angezeigte_stufe_nicht_rohe():
    """Bei gehaltenem ORANGE (roh GELB) erklaert der Text ORANGE, nicht GELB."""
    service = _service()

    # ORANGE etablieren
    service.assess_reading(_reading(_T0, surface=-1.0, dew=-1.5), _T0)

    # Halten auf ORANGE (roh GELB, im Deadband)
    poll2 = _T0 + timedelta(seconds=10)
    assessment = service.assess_reading(_reading(poll2, surface=0.3, dew=-1.5), poll2)

    assert assessment.displayed_risk_level is RiskLevel.ORANGE
    # Erklärung muss ORANGE-Thematik enthalten ("Vereisung wahrscheinlich"),
    # nicht GELB ("Grenzwertiger Bereich") — sonst Widerspruch Farbe vs. Text.
    assert assessment.explanation is not None
    assert "Vereisung wahrscheinlich" in assessment.explanation
    assert "grenzwertig" not in assessment.explanation.lower()


# ---------------------------------------------------------------------------
# Entkopplung: Alarm-Generierung folgt der rohen Stufe
# ---------------------------------------------------------------------------


def test_risk_level_bleibt_roh_fuer_alarm_und_audit():
    """risk_level (roh) wird unveraendert persistiert — Alarm-Gen liest roh, nicht entprellt.

    Bei roh != displayed (Hysterese haelt) muss risk_level die rohe Stufe behalten,
    damit die Alarm-Ausloesung (die risk_level konsumiert) nicht durch die
    Anzeige-Hysterese veraendert wird (DTB-27 Trennung Alarm vs. Anzeige).
    """
    service = _service()

    # ORANGE etablieren
    service.assess_reading(_reading(_T0, surface=-1.0, dew=-1.5), _T0)

    # Halten auf ORANGE (roh GELB)
    poll2 = _T0 + timedelta(seconds=10)
    assessment = service.assess_reading(_reading(poll2, surface=0.3, dew=-1.5), poll2)

    # risk_level = roh (GELB), displayed = gehalten (ORANGE) — bewusst verschieden
    assert assessment.risk_level is RiskLevel.YELLOW
    assert assessment.displayed_risk_level is RiskLevel.ORANGE
