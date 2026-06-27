"""Gemeinsame Fixtures fuer die Integrations-/E2E-Tests (DTB-41, DTB-49).

Bewusst In-Memory statt MariaDB: alle Repos sind die InMemory-Doubles, sodass die
Integrations- und E2E-Tests ohne DB und ohne echtes G1 laufen. Die Schwellen kommen
aus der echten Default-Config (load_thresholds) — keine Hardcodes (NF-05).

Alle Fixtures sind opt-in (kein autouse): bestehende Test-Module mit eigenen,
gleichnamigen Fixtures (z. B. `thresholds` in test_assessment_service.py, das autouse
`frozen_now` in test_ingest.py) ueberschatten diese conftest-Fixtures lokal und bleiben
unveraendert.
"""

from datetime import UTC, datetime

import pytest

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator
from src.assessment.service import AssessmentService
from src.config.loader import Thresholds, load_thresholds
from src.ingest.poller import Poller
from src.main import Runtime
from src.storage.acknowledgement_repository import InMemoryAcknowledgementRepository
from src.storage.alarm_repository import InMemoryAlarmRepository
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository
from src.storage.repository import InMemoryReadingRepository

# Single-Sensor-Betrieb (anr-rwy-01) — identisch zu src.main._SENSOR_ID.
_SENSOR_ID = "anr-rwy-01"


@pytest.fixture
def sensor_id() -> str:
    return _SENSOR_ID


@pytest.fixture
def thresholds() -> Thresholds:
    # Echte Default-Config (config/thresholds.json) — keine Hardcodes (NF-05).
    return load_thresholds()


@pytest.fixture
def reading_repo() -> InMemoryReadingRepository:
    return InMemoryReadingRepository()


@pytest.fixture
def assessment_repo() -> InMemoryAssessmentRepository:
    return InMemoryAssessmentRepository()


@pytest.fixture
def audit_repo() -> InMemoryAuditRepository:
    return InMemoryAuditRepository()


@pytest.fixture
def assessment_service(
    thresholds: Thresholds,
    assessment_repo: InMemoryAssessmentRepository,
    audit_repo: InMemoryAuditRepository,
) -> AssessmentService:
    # Teilt sich assessment_repo/audit_repo mit den gleichnamigen Fixtures, damit ein
    # Test nach assess_reading direkt den Repo-Zustand inspizieren kann (gleiche Instanz).
    return AssessmentService(thresholds, assessment_repo, audit_repo)


@pytest.fixture
def poller(reading_repo: InMemoryReadingRepository, thresholds: Thresholds) -> Poller:
    # Teilt sich reading_repo mit der gleichnamigen Fixture (gleiche Instanz).
    return Poller(
        base_url="http://g1.test",
        repository=reading_repo,
        data_quality_thresholds=thresholds.datenqualitaet,
        plausibility_thresholds=thresholds.plausibilitaet,
    )


@pytest.fixture
def alarm_repo() -> InMemoryAlarmRepository:
    return InMemoryAlarmRepository()


@pytest.fixture
def ack_repo(alarm_repo: InMemoryAlarmRepository) -> InMemoryAcknowledgementRepository:
    # Teilt den Alarm-Speicher mit alarm_repo, damit Quittierungs-Tests den Zustand
    # des zuvor gespeicherten Alarms veraendern koennen.
    return InMemoryAcknowledgementRepository(alarm_repo)


@pytest.fixture
def alarm_generator(
    thresholds: Thresholds,
    alarm_repo: InMemoryAlarmRepository,
    audit_repo: InMemoryAuditRepository,
) -> AlarmGenerator:
    # In-Memory-AlarmGenerator (DTB-27): Hysterese aus echter Config, geteiltes
    # In-Memory-Alarm-Repo, geteiltes audit_repo — analog build_runtime, aber ohne DB.
    return AlarmGenerator(AlarmHysterese(thresholds.hysterese), alarm_repo, audit_repo)


@pytest.fixture
def runtime(
    thresholds: Thresholds,
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    audit_repo: InMemoryAuditRepository,
    ack_repo: InMemoryAcknowledgementRepository,
    poller: Poller,
    assessment_service: AssessmentService,
    alarm_generator: AlarmGenerator,
) -> Runtime:
    # Vollstaendiger Runtime-Graph mit In-Memory-Repos; teilt alle Instanzen mit den
    # Einzelfixtures, sodass poller.poll() + service.assess_reading() und die spaetere
    # Endpoint-Abfrage denselben Speicher sehen (echter Pipeline-Pfad ohne DB).
    return Runtime(
        thresholds=thresholds,
        reading_repo=reading_repo,
        assessment_repo=assessment_repo,
        audit_repo=audit_repo,
        ack_repo=ack_repo,
        poller=poller,
        service=assessment_service,
        alarm_generator=alarm_generator,
    )


@pytest.fixture
def frozen_now() -> datetime:
    # Fester, zeitzonenbewusster UTC-Zeitstempel fuer deterministische Tests
    # (gleicher Wert wie die eingefrorene Uhr in test_ingest.py: 10:01:00).
    return datetime(2026, 6, 23, 10, 1, 0, tzinfo=UTC)
