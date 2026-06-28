"""Tests fuer das Quittierungs-Repository (DTB-24, FA-10, NF-09).

Belegt die DB-agnostische Naht ueber das In-Memory-Double: Quittieren eines aktiven
Alarms (State-Wechsel + acknowledgement-Eintrag + Audit), die fachlichen Fehler
(nicht gefunden -> AlarmNotFoundError; nicht aktiv -> AlarmNotAcknowledgeableError),
Double-Ack (NF-09) und die Append-only-/Atomaritaets-Eigenschaften.

Die MySQL-Variante (rohes PyMySQL, EINE transaction) wird gegen eine echte MariaDB
geprueft, sobald die DB-Integrationsfixtures greifen (Muster der uebrigen MySql-Repos).
"""

from datetime import UTC, datetime

import pytest

from src.model.enums import AlarmState, AuditEventType
from src.storage.acknowledgement_repository import (
    AlarmNotAcknowledgeableError,
    AlarmNotFoundError,
    InMemoryAcknowledgementRepository,
)

_NOW = datetime(2026, 6, 28, 3, 0, 0, tzinfo=UTC)


def test_acknowledge_active_alarm_persists_and_flips_state():
    repo = InMemoryAcknowledgementRepository({1: AlarmState.ACTIVE})

    ack = repo.acknowledge(1, "tower-ops-01", "Sichtkontrolle eingeleitet", _NOW)

    assert ack.id == 1
    assert ack.alarm_id == 1
    assert ack.operator == "tower-ops-01"
    assert ack.note == "Sichtkontrolle eingeleitet"
    assert ack.ts == _NOW
    # State-Wechsel active -> acknowledged.
    assert repo.state_of(1) is AlarmState.ACKNOWLEDGED
    # Genau eine Quittierung + ein Audit-Eintrag (NF-09, alarm_acknowledged).
    assert len(repo.acknowledgements) == 1
    assert len(repo.audit_entries) == 1
    audit = repo.audit_entries[0]
    assert audit.event_type is AuditEventType.ALARM_ACKNOWLEDGED
    assert audit.entity_type == "alarm"
    assert audit.entity_id == 1
    assert audit.actor == "tower-ops-01"


def test_acknowledge_accepts_missing_note():
    repo = InMemoryAcknowledgementRepository({7: AlarmState.ACTIVE})

    ack = repo.acknowledge(7, "tower-ops-02", None, _NOW)

    assert ack.note is None
    assert repo.state_of(7) is AlarmState.ACKNOWLEDGED


def test_acknowledge_unknown_alarm_raises_not_found():
    repo = InMemoryAcknowledgementRepository()

    with pytest.raises(AlarmNotFoundError):
        repo.acknowledge(99, "tower-ops-01", None, _NOW)
    # Nichts angelegt (kein Seiteneffekt bei fachlichem Fehler).
    assert repo.acknowledgements == []
    assert repo.audit_entries == []


@pytest.mark.parametrize("state", [AlarmState.ACKNOWLEDGED, AlarmState.CLEARED])
def test_acknowledge_non_active_alarm_raises_conflict(state: AlarmState):
    repo = InMemoryAcknowledgementRepository({1: state})

    with pytest.raises(AlarmNotAcknowledgeableError) as exc_info:
        repo.acknowledge(1, "tower-ops-01", None, _NOW)
    # Die Exception traegt den aktuellen Zustand (fuer die contract-konforme 409-Meldung).
    assert exc_info.value.state is state
    assert exc_info.value.alarm_id == 1
    # State unveraendert, kein Eintrag.
    assert repo.state_of(1) is state
    assert repo.acknowledgements == []


def test_double_ack_is_rejected_second_time():
    repo = InMemoryAcknowledgementRepository({1: AlarmState.ACTIVE})

    repo.acknowledge(1, "tower-ops-01", None, _NOW)
    # Zweite Quittierung desselben Alarms -> 409-Aequivalent (NF-09, nicht idempotent).
    with pytest.raises(AlarmNotAcknowledgeableError):
        repo.acknowledge(1, "tower-ops-09", None, _NOW)
    # Genau EINE Quittierung blieb bestehen (kein doppelter Eintrag).
    assert len(repo.acknowledgements) == 1


def test_seed_dict_is_not_mutated():
    # Der Konstruktor kopiert den Seed -> ein vom Aufrufer gehaltenes dict bleibt unberuehrt.
    seed = {1: AlarmState.ACTIVE}
    repo = InMemoryAcknowledgementRepository(seed)

    repo.acknowledge(1, "tower-ops-01", None, _NOW)

    assert seed[1] is AlarmState.ACTIVE  # Original nicht mutiert
    assert repo.state_of(1) is AlarmState.ACKNOWLEDGED  # nur der interne Stand
