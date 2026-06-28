"""Integrationstest AssessmentService -> Repositories (DTB-41, Teil 2).

Belegt das Zusammenspiel von ReadingRepository + AssessmentService +
AssessmentRepository + AuditRepository (alle In-Memory, echte Instanzen). Im
Gegensatz zu test_assessment_service.py (Unit, das die reading_id von Hand auf 1
setzt) wird das Reading hier ueber reading_repo.save() persistiert und so die
WIRKLICH vergebene id durch die Bewertung gereicht — der reale Pipeline-Pfad
(Poller persistiert -> Service bewertet das persistierte Reading).

Geprueft wird die Cross-Repo-Verdrahtung: korrekte Bewertung im assessment_repo,
reading_id-Verknuepfung auf die echte Reading-id und das assessment_made-Audit-Event.
Fail-safe (None/fault/stale -> unknown, nie GRUEN) wird ueber denselben Pfad belegt.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.assessment.service import AssessmentService
from src.config.loader import Thresholds
from src.model.enums import AuditEventType, RiskLevel, SensorStatus
from src.model.schemas import Reading
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository
from src.storage.repository import InMemoryReadingRepository


def _make_reading(
    measured_at: datetime,
    *,
    surface: float = 2.0,
    dew: float | None = 0.0,
    status: SensorStatus = SensorStatus.OK,
) -> Reading:
    # id=None: noch nicht persistiert; reading_repo.save() vergibt sie (wie der Poller).
    return Reading(
        sensor_id="anr-rwy-01",
        measured_at=measured_at,
        surface_temp_c=surface,
        air_temp_c=3.0,
        humidity_pct=80.0,
        received_at=measured_at,
        dew_point_c=dew,
        status=status,
    )


def _persist(reading_repo: InMemoryReadingRepository, reading: Reading) -> Reading:
    # Spiegelt den Poller: speichern -> Reading MIT vergebener id zurueck.
    new_id = reading_repo.save(reading)
    return reading.model_copy(update={"id": new_id})


def test_healthy_reading_links_assessment_to_persisted_reading(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    audit_repo: InMemoryAuditRepository,
    assessment_service: AssessmentService,
) -> None:
    now = datetime.now(UTC)
    # T_s=2.0 (>1.0), Taupunkt 0.0 -> delta_t=2.0 trocken -> GRUEN.
    persisted = _persist(reading_repo, _make_reading(now, surface=2.0, dew=0.0))

    result = assessment_service.assess_reading(persisted, now)

    assert result.risk_level == RiskLevel.GREEN
    latest = assessment_repo.get_latest()
    assert latest is not None
    assert latest.risk_level == RiskLevel.GREEN
    # Cross-Repo-Verdrahtung: das Assessment verweist auf die ECHTE Reading-id.
    assert latest.reading_id == persisted.id
    events = audit_repo.all()
    assert len(events) == 1
    assert events[0].event_type == AuditEventType.ASSESSMENT_MADE


def test_none_reading_persists_unknown_without_reading_link(
    assessment_repo: InMemoryAssessmentRepository,
    audit_repo: InMemoryAuditRepository,
    assessment_service: AssessmentService,
) -> None:
    # Kein Reading (G1 nicht erreichbar) -> unknown ohne reading_id (kein Bezug moeglich).
    result = assessment_service.assess_reading(None, datetime.now(UTC))

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id is None
    latest = assessment_repo.get_latest()
    assert latest is not None
    assert latest.risk_level == RiskLevel.UNKNOWN
    assert any(e.event_type == AuditEventType.ASSESSMENT_MADE for e in audit_repo.all())


def test_fault_reading_persists_unknown_linked_to_reading(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    assessment_service: AssessmentService,
) -> None:
    now = datetime.now(UTC)
    # Werte, die fresh GRUEN ergaeben; fault muss sie ueberstimmen (NF-01, nie GRUEN).
    persisted = _persist(
        reading_repo, _make_reading(now, surface=20.0, dew=0.0, status=SensorStatus.FAULT)
    )

    result = assessment_service.assess_reading(persisted, now)

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id == persisted.id  # ausloesendes Reading verknuepft (Traceability)
    assert assessment_repo.get_latest().risk_level == RiskLevel.UNKNOWN


def test_vorfall_1_fehlalarm_vermieden_im_service_pfad(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    audit_repo: InMemoryAuditRepository,
    assessment_service: AssessmentService,
) -> None:
    """Vorfall 1 (Quelle): Luft -2,1 °C, Oberflaeche trocken -> KEIN ROT/Alarm.

    Fruehere reine Lufttemperatur-/RH-Logik haette fälschlich ROT/Alarm ausgeloest.
    Hier wird ueber den vollstaendigen Service-Pfad (Persistenz + Audit) belegt,
    dass die Bewertung auf GELB faellt (kalt, aber nicht feucht) und KEIN Audit-
    Ereignis vom Typ alarm_raised entsteht. Das ist der Fehlalarm-Verhinderungs-
    Beweis durch T_s + DeltaT statt Lufttemperatur (E-34).
    """
    now = datetime.now(UTC)
    persisted = _persist(reading_repo, _make_reading(now, surface=-2.1, dew=-10.0))

    result = assessment_service.assess_reading(persisted, now)

    assert result.risk_level == RiskLevel.YELLOW
    assert result.reading_id == persisted.id
    latest = assessment_repo.get_latest()
    assert latest is not None and latest.risk_level == RiskLevel.YELLOW
    assert latest.delta_t == pytest.approx(7.9)
    events = audit_repo.all()
    assert len(events) == 1
    assert events[0].event_type == AuditEventType.ASSESSMENT_MADE
    # Der AssessmentService schreibt nur ASSESSMENT_MADE; alarm_raised kommt vom
    # separaten AlarmGenerator (Test hier bewusst nur auf Service-Ebene). Der
    # Fehlalarm-Beweis ist das risk_level=YELLOW (kein ROT), nicht die Abwesenheit
    # eines Alarm-Events.


def test_vorfall_2_vereisung_erkannt_im_service_pfad(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    audit_repo: InMemoryAuditRepository,
    assessment_service: AssessmentService,
) -> None:
    """Vorfall 2 (Quelle): Luft +1,2 °C, aber Oberflaeche gefroren + Reif -> ROT.

    Fruehere Logik, die auf Lufttemperatur > 0 °C vertraute, hat diese Eisbildung
    uebersehen. Hier wird ueber den vollstaendigen Service-Pfad belegt, dass die
    Bewertung korrekt auf ROT faellt (Oberflaeche <= Gefrierpunkt UND DeltaT <= 0)
    und die Explanation DeltaT erwaehnt — der Wert, der die beiden Vorfälle
    unterscheidet und Fehlalarme verhindert (E-34, NF-01).
    """
    now = datetime.now(UTC)
    persisted = _persist(reading_repo, _make_reading(now, surface=-1.0, dew=-0.5))

    result = assessment_service.assess_reading(persisted, now)

    assert result.risk_level == RiskLevel.RED
    assert result.reading_id == persisted.id
    latest = assessment_repo.get_latest()
    assert latest is not None and latest.risk_level == RiskLevel.RED
    assert latest.delta_t == pytest.approx(-0.5)
    # DeltaT muss im operatorlesbaren Explanation-Text stehen (Fehlalarm-Verhinderungs-Feature).
    assert latest.explanation is not None and "ΔT" in latest.explanation
    assert any(e.event_type == AuditEventType.ASSESSMENT_MADE for e in audit_repo.all())


def test_stale_reading_persists_unknown_linked_to_reading(
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    assessment_service: AssessmentService,
    thresholds: Thresholds,
) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(seconds=thresholds.datenqualitaet.stale_timeout_s + 60)
    # Warmes (waere GRUEN), aber veraltetes Reading -> unknown (NF-01).
    persisted = _persist(reading_repo, _make_reading(old, surface=20.0, dew=0.0))

    result = assessment_service.assess_reading(persisted, now)

    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.reading_id == persisted.id
    assert assessment_repo.get_latest().risk_level == RiskLevel.UNKNOWN
