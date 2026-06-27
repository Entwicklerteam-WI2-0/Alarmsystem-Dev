"""Persistenz fuer Alarm-Quittierungen (DTB-63, NF-09).

Quittieren ist eine manuelle UI-Aktion; das Repository fuehrt den Zustandswechsel
`active -> acknowledged` sowie den append-only Acknowledgement-Eintrag durch.
Es wird bewusst von `AlarmRepository` getrennt, damit das Alarm-Repository-
Interface save-only bleibt (RB-01).
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime

import pymysql

from src.model.enums import AlarmState
from src.model.schemas import Acknowledgement, Alarm
from src.storage.alarm_repository import InMemoryAlarmRepository
from src.storage.database import (
    DatabaseConfig,
    DatabaseConfigError,
    DatabaseConnectionError,
    transaction,
)
from src.storage.repository import RepositoryError

_SELECT_ALARM_SQL = """
    SELECT id, assessment_id, severity, raised_at, state
    FROM alarm
    WHERE id = %s
"""

_UPDATE_STATE_SQL = """
    UPDATE alarm
    SET state = %s
    WHERE id = %s
"""

_INSERT_ACK_SQL = """
    INSERT INTO acknowledgement (alarm_id, operator, note, ts)
    VALUES (%s, %s, %s, %s)
"""


class AlarmNotFoundError(ValueError):
    """Alarm mit der angegebenen ID existiert nicht."""


class AlarmAlreadyAcknowledgedError(ValueError):
    """Alarm ist nicht mehr aktiv (bereits quittiert oder geschlossen)."""


class AcknowledgementRepository(ABC):
    """Abstrakte Persistenz fuer Alarm-Quittierungen."""

    @abstractmethod
    def acknowledge(
        self, alarm_id: int, operator: str, note: str | None, ts: datetime
    ) -> Acknowledgement:
        """Quittiert einen aktiven Alarm.

        Raises:
            AlarmNotFoundError: Alarm nicht vorhanden.
            AlarmAlreadyAcknowledgedError: Alarm nicht mehr aktiv.
            RepositoryError: DB-Fehler.
        """
        ...


class InMemoryAcknowledgementRepository(AcknowledgementRepository):
    """In-Memory-Double fuer Quittierungen.

    Teilt sich bewusst den Alarm-Speicher mit `InMemoryAlarmRepository`, damit
    Tests den vollen Zyklus alarmieren -> quittieren durchspielen koennen.
    """

    def __init__(self, alarm_repo: object | None = None) -> None:
        self._alarm_repo = alarm_repo
        self._own_alarms: list[Alarm] = []
        self._acks: list[Acknowledgement] = []
        self._next_ack_id = 0

    def acknowledge(
        self, alarm_id: int, operator: str, note: str | None, ts: datetime
    ) -> Acknowledgement:
        alarm = self._find_alarm(alarm_id)
        if alarm is None:
            raise AlarmNotFoundError(f"Alarm {alarm_id} nicht gefunden")
        if alarm.state is not AlarmState.ACTIVE:
            raise AlarmAlreadyAcknowledgedError(
                f"Alarm {alarm_id} ist bereits im Zustand '{alarm.state.value}'"
            )
        alarm.state = AlarmState.ACKNOWLEDGED
        self._next_ack_id += 1
        ack = Acknowledgement(
            id=self._next_ack_id,
            alarm_id=alarm_id,
            operator=operator,
            note=note,
            ts=ts.astimezone(UTC),
        )
        self._acks.append(ack.model_copy())
        return ack.model_copy()

    def _find_alarm(self, alarm_id: int) -> Alarm | None:
        if self._alarm_repo is not None:
            if isinstance(self._alarm_repo, InMemoryAlarmRepository):
                return self._alarm_repo.get(alarm_id)
            raise TypeError(
                "InMemoryAcknowledgementRepository erwartet InMemoryAlarmRepository "
                f"oder None, erhielt {type(self._alarm_repo).__name__}"
            )
        for alarm in self._own_alarms:
            if alarm.id == alarm_id:
                return alarm
        return None


class MySqlAcknowledgementRepository(AcknowledgementRepository):
    """MySQL-Implementierung der Quittierungs-Persistenz (DTB-63, E-35)."""

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        self._config = config

    def acknowledge(
        self, alarm_id: int, operator: str, note: str | None, ts: datetime
    ) -> Acknowledgement:
        params = (
            alarm_id,
            operator,
            note,
            ts.astimezone(UTC),
        )
        try:
            with transaction(self._config) as conn, conn.cursor() as cursor:
                cursor.execute(_SELECT_ALARM_SQL, (alarm_id,))
                row = cursor.fetchone()
                if row is None:
                    raise AlarmNotFoundError(f"Alarm {alarm_id} nicht gefunden")
                state = AlarmState(row["state"])
                if state is not AlarmState.ACTIVE:
                    raise AlarmAlreadyAcknowledgedError(
                        f"Alarm {alarm_id} ist bereits im Zustand '{state.value}'"
                    )
                cursor.execute(_UPDATE_STATE_SQL, (AlarmState.ACKNOWLEDGED.value, alarm_id))
                cursor.execute(_INSERT_ACK_SQL, params)
                row_id = cursor.lastrowid
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            raise RepositoryError(
                f"Quittierung fuer Alarm {alarm_id} konnte nicht gespeichert werden"
            ) from exc
        except ValueError:
            raise
        if not row_id:
            raise RepositoryError("Quittierung wurde ohne gueltige ID gespeichert")
        return Acknowledgement(
            id=int(row_id),
            alarm_id=alarm_id,
            operator=operator,
            note=note,
            ts=ts.astimezone(UTC),
        )
