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
from src.api.broadcaster import AlarmBroadcaster
from src.assessment.service import AssessmentService
from src.config.loader import Thresholds, load_thresholds
from src.ingest.poller import Poller
from src.main import _SENSOR_ID, Runtime
from src.storage.alarm_repository import InMemoryAlarmRepository
from src.storage.assessment_repository import InMemoryAssessmentRepository
from src.storage.audit_repository import InMemoryAuditRepository
from src.storage.repository import InMemoryReadingRepository
from src.storage.threshold_set_repository import InMemoryThresholdSetRepository


@pytest.fixture
def sensor_id() -> str:
    # Aus src.main importiert (kein Duplikat -> kein Drift bei einem Sensor-Rename).
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
def threshold_set_repo() -> InMemoryThresholdSetRepository:
    return InMemoryThresholdSetRepository()


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
def alarm_generator(thresholds: Thresholds, audit_repo: InMemoryAuditRepository) -> AlarmGenerator:
    # In-Memory-AlarmGenerator (DTB-27): Hysterese aus echter Config, In-Memory-Alarm-Repo,
    # geteiltes audit_repo — analog build_runtime, aber ohne DB.
    return AlarmGenerator(
        AlarmHysterese(thresholds.hysterese), InMemoryAlarmRepository(), audit_repo
    )


@pytest.fixture
def alarm_broadcaster() -> AlarmBroadcaster:
    # Live-Alarm-Broadcaster (DTB-61): In-Memory Pub/Sub, kontaktiert nichts.
    return AlarmBroadcaster()


@pytest.fixture
def runtime(
    thresholds: Thresholds,
    reading_repo: InMemoryReadingRepository,
    assessment_repo: InMemoryAssessmentRepository,
    audit_repo: InMemoryAuditRepository,
    threshold_set_repo: InMemoryThresholdSetRepository,
    poller: Poller,
    assessment_service: AssessmentService,
    alarm_generator: AlarmGenerator,
    alarm_broadcaster: AlarmBroadcaster,
) -> Runtime:
    # Vollstaendiger Runtime-Graph mit In-Memory-Repos; teilt alle Instanzen mit den
    # Einzelfixtures, sodass poller.poll() + service.assess_reading() und die spaetere
    # Endpoint-Abfrage denselben Speicher sehen (echter Pipeline-Pfad ohne DB).
    return Runtime(
        thresholds=thresholds,
        reading_repo=reading_repo,
        assessment_repo=assessment_repo,
        audit_repo=audit_repo,
        threshold_set_repo=threshold_set_repo,
        poller=poller,
        service=assessment_service,
        alarm_generator=alarm_generator,
        alarm_broadcaster=alarm_broadcaster,
    )


@pytest.fixture
def frozen_now() -> datetime:
    # Fester, zeitzonenbewusster UTC-Zeitstempel fuer deterministische Tests
    # (gleicher Wert wie die eingefrorene Uhr in test_ingest.py: 10:01:00).
    return datetime(2026, 6, 23, 10, 1, 0, tzinfo=UTC)
