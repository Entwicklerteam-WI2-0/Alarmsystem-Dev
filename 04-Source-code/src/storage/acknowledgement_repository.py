"""Persistenz der Alarm-Quittierung (DTB-24 / FA-10, NF-09 append-only).

Quittieren ist ein Zustandswechsel am Alarm (`active -> acknowledged`) PLUS ein
unveraenderlicher `acknowledgement`-Eintrag PLUS ein `alarm_acknowledged`-Audit-Eintrag.
Diese drei Schreibvorgaenge muessen atomar sein (EINE Transaktion), sonst kann ein
Teil-Schreiben einen Alarm als `acknowledged` markieren ohne Quittierungs-/Audit-Beleg
(NF-09-Luecke). Die MySQL-Implementierung kapselt das in EINER `transaction()`.

RB-01: rein dokumentierende Quittierung (UI/Audit) — KEIN Aktor, keine Bahnfreigabe.

append-only (NF-09): die `acknowledgement`-Tabelle wird nur per INSERT geschrieben (kein
UPDATE/DELETE); zweite Absicherung auf DB-Ebene via Grants (migrations/grants.sql, DTB-54).
Der `alarm.state`-UPDATE ist davon unberuehrt (State-Maschine, kein Audit-Trail).

Muster wie src/storage/alarm_repository.py / audit_repository.py.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime

import pymysql

from src.model.enums import AlarmState, AuditEventType
from src.model.schemas import Acknowledgement, AuditLogEntry
from src.storage.database import (
    DatabaseConfig,
    DatabaseConfigError,
    DatabaseConnectionError,
    transaction,
)
from src.storage.repository import RepositoryError


class AlarmNotFoundError(Exception):
    """Der zu quittierende Alarm existiert nicht (-> Endpoint 404)."""


class AlarmNotAcknowledgeableError(Exception):
    """Der Alarm ist nicht im Zustand `active` (bereits acknowledged/cleared) -> 409.

    Traegt den aktuellen Zustand, damit der Endpoint eine contract-konforme, nicht-leakende
    409-Meldung bauen kann (NF-09: erneute Quittierung wird abgelehnt, nicht still geschluckt).
    """

    def __init__(self, alarm_id: int, state: AlarmState) -> None:
        self.alarm_id = alarm_id
        self.state = state
        super().__init__(
            f"Alarm {alarm_id} ist bereits im Zustand '{state.value}' "
            "(erneute Quittierung abgelehnt)"
        )


class AcknowledgementRepository(ABC):
    """Abstrakte Persistenz der Alarm-Quittierung. Eine Methode: `acknowledge`.

    Sie fuehrt den vollstaendigen Quittierungs-Vorgang atomar aus (State-Wechsel +
    `acknowledgement`-Eintrag + Audit) und meldet die fachlichen Fehler als Domaenen-
    Exceptions (`AlarmNotFoundError` / `AlarmNotAcknowledgeableError`), damit der API-Layer
    sie contract-konform auf 404/409 abbilden kann.
    """

    @abstractmethod
    def acknowledge(
        self, alarm_id: int, operator: str, note: str | None, now: datetime
    ) -> Acknowledgement:
        """Quittiert einen aktiven Alarm und gibt den persistierten Eintrag zurueck.

        Args:
            alarm_id: ID des zu quittierenden Alarms.
            operator: Quittierende Person (Audit-Anker, Pflicht).
            note: Optionale Freitext-Notiz.
            now: Quittierungs-Zeitpunkt (UTC, zeitzonenbewusst).

        Raises:
            AlarmNotFoundError: Kein Alarm mit dieser ID.
            AlarmNotAcknowledgeableError: Alarm nicht im Zustand `active`.
            RepositoryError: Persistenz-/DB-Fehler (fail-safe).
        """
        ...


class InMemoryAcknowledgementRepository(AcknowledgementRepository):
    """In-Memory-Double fuer DB-freie Tests/Laeufe.

    Haelt einen Alarm-Zustands-Index (seedbar ueber den Konstruktor) sowie die erzeugten
    Quittierungen und Audit-Eintraege, sodass Endpoint-Tests den Effekt ohne DB inspizieren
    koennen. Spiegelt die Atomaritaet der MySQL-Variante: bei einem fachlichen Fehler (nicht
    aktiv / nicht gefunden) wird nichts veraendert.
    """

    def __init__(self, alarm_states: dict[int, AlarmState] | None = None) -> None:
        # Kopie statt Aliasing: ein vom Test uebergebenes dict wird nicht mutiert.
        self._alarm_states: dict[int, AlarmState] = dict(alarm_states or {})
        self.acknowledgements: list[Acknowledgement] = []
        self.audit_entries: list[AuditLogEntry] = []

    def acknowledge(
        self, alarm_id: int, operator: str, note: str | None, now: datetime
    ) -> Acknowledgement:
        state = self._alarm_states.get(alarm_id)
        if state is None:
            raise AlarmNotFoundError(f"Alarm {alarm_id} nicht gefunden")
        if state is not AlarmState.ACTIVE:
            raise AlarmNotAcknowledgeableError(alarm_id, state)
        # Atomar (in-memory trivial): State -> acknowledged, Eintrag + Audit anlegen.
        self._alarm_states[alarm_id] = AlarmState.ACKNOWLEDGED
        ack = Acknowledgement(
            id=len(self.acknowledgements) + 1,
            alarm_id=alarm_id,
            operator=operator,
            note=note,
            ts=now,
        )
        self.acknowledgements.append(ack)
        self.audit_entries.append(
            AuditLogEntry(
                ts=now,
                event_type=AuditEventType.ALARM_ACKNOWLEDGED,
                entity_type="alarm",
                entity_id=alarm_id,
                actor=operator,
                detail={"acknowledgement_id": ack.id},
            )
        )
        return ack

    def state_of(self, alarm_id: int) -> AlarmState | None:
        """Aktueller (Test-)Zustand eines Alarms — nur fuer Assertions im Double."""
        return self._alarm_states.get(alarm_id)


class MySqlAcknowledgementRepository(AcknowledgementRepository):
    """Alarm-Quittierung auf MariaDB/MySQL via rohem PyMySQL (DTB-24, E-35).

    Fuehrt State-Wechsel (`alarm.state -> acknowledged`), den `acknowledgement`-INSERT und
    den `alarm_acknowledged`-Audit-INSERT in EINER Transaktion aus (Atomaritaet, NF-09).
    Der Alarm wird mit `SELECT ... FOR UPDATE` gesperrt, damit zwei gleichzeitige
    Quittierungen nicht beide am State-Check vorbeikommen (Double-Ack-Race -> 409 bleibt
    verlaesslich). Alle Queries sind parametrisiert (Injection-Schutz, nie String-Format).
    """

    _SELECT_ALARM_SQL = "SELECT state FROM alarm WHERE id = %s FOR UPDATE"
    _UPDATE_ALARM_SQL = "UPDATE alarm SET state = %s WHERE id = %s"
    _INSERT_ACK_SQL = (
        "INSERT INTO acknowledgement (alarm_id, operator, note, ts) VALUES (%s, %s, %s, %s)"
    )
    # Audit-INSERT inline in DERSELBEN Transaktion (NICHT ueber MySqlAuditRepository.append,
    # das eine EIGENE Transaktion oeffnete -> waere nicht atomar mit dem State-Wechsel).
    # Spalten = migrations/schema.sql (audit_log). Konsolidierung auf einen geteilten
    # write_audit_entry(cursor, entry)-Helper, sobald dieser zentral verfuegbar ist (DTB-63).
    _INSERT_AUDIT_SQL = (
        "INSERT INTO audit_log (ts, event_type, entity_type, entity_id, actor, detail) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        # Optionale Config (sonst aus Env via database.py); erleichtert Tests.
        self._config = config

    def acknowledge(
        self, alarm_id: int, operator: str, note: str | None, now: datetime
    ) -> Acknowledgement:
        try:
            with transaction(self._config) as conn, conn.cursor() as cursor:
                cursor.execute(self._SELECT_ALARM_SQL, (alarm_id,))
                row = cursor.fetchone()
                if row is None:
                    raise AlarmNotFoundError(f"Alarm {alarm_id} nicht gefunden")
                try:
                    state = AlarmState(row["state"])
                except ValueError as exc:
                    # Korrupter/unbekannter DB-state (manuelle Migration, Schema-Drift): das ist
                    # ein Repository-/Persistenzfehler, kein API-Fehler. Als RepositoryError
                    # fail-safe herunterbrechen (Endpoint -> 503 Error{code,message}, NF-01/
                    # Contract D), statt FastAPI ein rohes 500/{detail} werfen zu lassen. Das
                    # raise rollt die Transaktion zurueck (kein Teil-Schreiben).
                    raise RepositoryError(
                        f"Unbekannter Alarm-Zustand in DB: {row['state']!r}"
                    ) from exc
                if state is not AlarmState.ACTIVE:
                    raise AlarmNotAcknowledgeableError(alarm_id, state)

                cursor.execute(self._UPDATE_ALARM_SQL, (AlarmState.ACKNOWLEDGED.value, alarm_id))
                cursor.execute(self._INSERT_ACK_SQL, (alarm_id, operator, note, now))
                ack_id = cursor.lastrowid
                if not ack_id:
                    # Kein gueltiger AUTO_INCREMENT-Wert -> Transaktion verwerfen (das raise
                    # loest den Rollback im transaction-Kontext aus), statt eine ID-lose
                    # Quittierung zu bestaetigen (NF-01 konsistenter Zustand).
                    raise RepositoryError("Quittierung wurde ohne gueltige ID gespeichert")
                cursor.execute(
                    self._INSERT_AUDIT_SQL,
                    (
                        now,
                        AuditEventType.ALARM_ACKNOWLEDGED.value,
                        "alarm",
                        alarm_id,
                        operator,
                        json.dumps({"acknowledgement_id": int(ack_id)}),
                    ),
                )
        except (AlarmNotFoundError, AlarmNotAcknowledgeableError):
            # Fachliche Fehler NICHT als RepositoryError maskieren — der Endpoint braucht sie
            # fuer 404/409. Die Transaktion wurde durch das raise bereits zurueckgerollt.
            raise
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            # Bekannte DB-Fehler (Verbindung, Config, CHECK/FK, Broken-Pipe) fail-safe auf die
            # Domaenen-Exception herunterbrechen (NF-01), nie als roher Treiberfehler nach aussen.
            raise RepositoryError("Quittierung konnte nicht gespeichert werden") from exc
        return Acknowledgement(
            id=int(ack_id), alarm_id=alarm_id, operator=operator, note=note, ts=now
        )
