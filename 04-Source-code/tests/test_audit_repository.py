"""Tests fuer das append-only Audit-Log-Repository (DTB-29 / NF-09).

Kernverhalten (Tagebuch-Prinzip): Eintraege koennen NUR angehaengt werden.
Es gibt bewusst KEIN Aendern und KEIN Loeschen -- append-only schon per Design
der Schnittstelle (zweite Absicherung folgt auf DB-Ebene via Trigger/Grants).
"""

from datetime import UTC, datetime

from src.model.enums import AuditEventType
from src.model.schemas import AuditLogEntry
from src.storage.audit_repository import AuditRepository, InMemoryAuditRepository

UTC_NOW = datetime(2026, 6, 25, 10, 0, 0, tzinfo=UTC)


def _entry(**overrides) -> AuditLogEntry:
    base = dict(
        ts=UTC_NOW,
        event_type=AuditEventType.ASSESSMENT_MADE,
        entity_type="assessment",
        entity_id=1,
    )
    base.update(overrides)
    return AuditLogEntry(**base)


def test_append_returns_generated_id():
    # Arrange
    repo = InMemoryAuditRepository()
    # Act
    new_id = repo.append(_entry())
    # Assert: das Speichermedium vergibt eine ID (wie AUTO_INCREMENT).
    assert new_id == 1


def test_appended_entries_are_readable_in_order():
    # Arrange
    repo = InMemoryAuditRepository()
    # Act
    repo.append(_entry(event_type=AuditEventType.READING_INGESTED))
    repo.append(_entry(event_type=AuditEventType.ALARM_RAISED))
    # Assert: beide Eintraege bleiben in Reihenfolge erhalten.
    events = [e.event_type for e in repo.all()]
    assert events == [AuditEventType.READING_INGESTED, AuditEventType.ALARM_RAISED]


def test_repository_is_append_only_by_design():
    # Assert: die Schnittstelle bietet KEIN update/delete -- nur anhaengen.
    # So kann ein Tagebuch-Eintrag per Design nicht geaendert/geloescht werden.
    assert not hasattr(AuditRepository, "update")
    assert not hasattr(AuditRepository, "delete")
