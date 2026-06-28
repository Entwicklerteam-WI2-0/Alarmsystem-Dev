"""Persistenz fuer ausgeloeste Alarme (DTB-27) + Resync-Lesepfad (DTB-31).

Speichert einen neu ausgeloesten Alarm (state='active') in MariaDB/MySQL via rohem
PyMySQL und parametrisiertem INSERT (E-35, Injection-Schutz) und liest Alarme fuer den
Resync-Backstop `GET /v1/alarms` (DTB-31). Bewusst nur `save` (Schreiben) + `get_alarms`
(Lesen): Zustandswechsel (DTB-24 ack/clear, RB-01 manuell) sind ein eigenes Ticket und
hier NICHT enthalten (kein UPDATE/DELETE-Pfad).

RB-01: Das Repository persistiert und liest nur — es fuehrt keine Aktor-/Steuer-Aktion
und keinen Zustandswechsel aus. Muster wie src/storage/audit_repository.py /
src/storage/assessment_repository.py.
"""

from abc import ABC, abstractmethod
from datetime import UTC
from typing import Any

import pymysql

from src.model.enums import AlarmState
from src.model.schemas import Alarm
from src.storage.database import (
    DatabaseConfig,
    DatabaseConfigError,
    DatabaseConnectionError,
    get_connection,
    transaction,
)
from src.storage.repository import RepositoryError

# Spaltenreihenfolge des INSERT -- entspricht migrations/schema.sql (alarm).
# id ist AUTO_INCREMENT und wird NICHT gesetzt; assessment_id..state parametrisiert.
_INSERT_SQL = (
    "INSERT INTO alarm (assessment_id, severity, raised_at, state) VALUES (%s, %s, %s, %s)"
)

# "Offene" Alarme fuer den Default-Resync (DTB-31): aktiv ODER quittiert (noch nicht
# beendet). cleared bleibt aussen vor -- sonst wuerden laengst beendete Alarme die
# G3-Resync-Ansicht fluten (Contract: ohne state-Filter nur OFFENE Alarme).
_OPEN_STATES = (AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED)
# IN-Platzhalter dynamisch aus der Cardinality ableiten -> SQL-Template und params-Tupel
# bleiben automatisch synchron, falls _OPEN_STATES je waechst/schrumpft (kein stiller Drift).
_OPEN_PLACEHOLDERS = ", ".join(["%s"] * len(_OPEN_STATES))

# Obergrenze fuer get_alarms — auch am Repo-Rand (Defense-in-Depth), nicht nur in der
# FastAPI-Schicht (Query le=500). Schuetzt interne Aufrufer vor unbegrenzten DB-Reads.
_MAX_ALARM_LIMIT = 500

# Lese-SQL fuer GET /v1/alarms (DTB-31). Spalten = Alarm-Wire-Felder; newest-first
# (raised_at DESC, id DESC als Tie-Break) -> stabiler, sinnvoller Resync (zuletzt
# ausgeloeste Alarme zuerst). LIMIT parametrisiert.
_SELECT_COLS = "id, assessment_id, severity, raised_at, state"
_ORDER_LIMIT = "ORDER BY raised_at DESC, id DESC LIMIT %s"
_SELECT_OPEN_SQL = (
    f"SELECT {_SELECT_COLS} FROM alarm WHERE state IN ({_OPEN_PLACEHOLDERS}) {_ORDER_LIMIT}"
)
_SELECT_BY_STATE_SQL = f"SELECT {_SELECT_COLS} FROM alarm WHERE state = %s {_ORDER_LIMIT}"


def _require_active(alarm: Alarm) -> None:
    """V8: nur ausgeloeste (aktive) Alarme werden persistiert.

    Ein nicht-aktiver Zustand beim Speichern ist ein Aufrufer-Fehler — Zustandswechsel
    (acknowledged/cleared) laufen ueber DTB-24/manuell (RB-01), nicht ueber save().
    """
    if alarm.state is not AlarmState.ACTIVE:
        raise ValueError(
            f"save() persistiert nur aktive Alarme; state={alarm.state.value} "
            "(Zustandswechsel laufen ueber DTB-24/manuell)"
        )


def _require_positive_limit(limit: int) -> None:
    """Gemeinsame Eingangspruefung fuer get_alarms (Repo-Rand, nicht nur via Endpoint)."""
    if limit < 1 or limit > _MAX_ALARM_LIMIT:
        raise ValueError(f"limit muss 1..{_MAX_ALARM_LIMIT} sein, war {limit}")


class AlarmRepository(ABC):
    """Abstrakte Alarm-Persistenz. Bewusst nur `save` (Schreiben) + `get_alarms` (Lesen)."""

    @abstractmethod
    def save(self, alarm: Alarm) -> int:
        """Speichert einen ausgeloesten Alarm und gibt die vergebene ID zurueck."""
        ...

    @abstractmethod
    def get_alarms(self, state: AlarmState | None = None, limit: int = 100) -> list[Alarm]:
        """Liest Alarme fuer den Resync (DTB-31, `GET /v1/alarms`).

        Args:
            state: Auf genau diesen Zustand filtern. `None` (Default) = alle OFFENEN
                Alarme (`active` + `acknowledged`, ohne `cleared`) -- der vollstaendige
                Resync nach SSE-Disconnect (E-37).
            limit: Maximale Anzahl zurueckgegebener Alarme (1..500).

        Returns:
            Alarme newest-first (zuletzt ausgeloeste zuerst); leere Liste, wenn keine.

        Raises:
            ValueError: Wenn `limit` ausserhalb 1..500 liegt.
            RepositoryError: Bei Datenbank- oder Mapping-Fehlern (fail-safe, NF-01).
        """
        ...


class InMemoryAlarmRepository(AlarmRepository):
    """In-Memory-Double fuer DB-freie Tests/Laeufe. Vergibt IDs ab 1.

    Bildet bewusst KEINE referenzielle Integritaet nach: eine nicht existierende
    `assessment_id` wird hier akzeptiert (das MySQL-Repository wuerde sie per FK ablehnen).
    Das Double ist daher kein Vollersatz fuer FK-/CHECK-Semantik (-> DTB-21-Integration).
    """

    def __init__(self) -> None:
        self._alarms: list[Alarm] = []
        self._next_id = 0

    def save(self, alarm: Alarm) -> int:
        _require_active(alarm)
        # Monoton steigender Zaehler (nicht len()+1): bleibt korrekt, falls spaetere
        # DTB-21-Fixtures Lösch-/Reset-Operationen einfuehren (sonst stille ID-Kollision).
        self._next_id += 1
        new_id = self._next_id
        # Alarm mit vergebener ID ablegen; das Original bleibt unangetastet.
        self._alarms.append(alarm.model_copy(update={"id": new_id}))
        return new_id

    def get_alarms(self, state: AlarmState | None = None, limit: int = 100) -> list[Alarm]:
        _require_positive_limit(limit)
        wanted = {state} if state is not None else set(_OPEN_STATES)
        matched = [alarm for alarm in self._alarms if alarm.state in wanted]
        # newest-first wie das MySQL-Repo: raised_at DESC, id als stabiler Tie-Break.
        matched.sort(key=lambda alarm: (alarm.raised_at, alarm.id or 0), reverse=True)
        # Kopien (Lese-Aliasing vermeiden), wie all(): der interne Stand bleibt unberuehrt.
        return [alarm.model_copy() for alarm in matched[:limit]]

    def all(self) -> list[Alarm]:
        """Liest alle Alarme in Einfuege-Reihenfolge (nur Double; YAGNI-Lesepfad).

        Gibt Kopien zurueck, damit der interne Stand nicht ueber die zurueckgegebenen
        (mutablen) Alarm-Objekte veraendert werden kann (Lese-Aliasing vermeiden).
        """
        return [alarm.model_copy() for alarm in self._alarms]


class MySqlAlarmRepository(AlarmRepository):
    """Alarm-Persistenz auf MariaDB/MySQL via rohem PyMySQL (DTB-27/DTB-31, E-35).

    Schreibt ausschliesslich per parametrisiertem INSERT (Injection-Schutz, nie
    String-Formatierung) und liest per parametrisiertem SELECT. Kein UPDATE-/DELETE-Pfad
    (Zustandswechsel = DTB-24/manuell).
    """

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        # Optionale Config (sonst aus Env via database.py); erleichtert Tests.
        self._config = config

    def save(self, alarm: Alarm) -> int:
        _require_active(alarm)
        params = (
            alarm.assessment_id,
            alarm.severity.value,
            alarm.raised_at,
            alarm.state.value,
        )
        try:
            with transaction(self._config) as conn, conn.cursor() as cursor:
                cursor.execute(_INSERT_SQL, params)
                # AUTO_INCREMENT-ID des gerade eingefuegten Alarms.
                row_id = cursor.lastrowid
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            # Verbindungs-, Config- UND Query-Fehler (z. B. CHECK-/FK-Verletzung,
            # Broken-Pipe) auf die Domaenen-Exception herunterbrechen, damit der Aufrufer
            # fail-safe reagieren kann (NF-01) statt mit rohem Treiberfehler zu crashen.
            # Ein Speicher-Fehler darf den Alarm nicht still verschlucken.
            # BEWUSST eng (Konvention aller Repos: Reading/Audit/Assessment fangen dieselbe
            # Trias): nur BEKANNTE DB-Fehler werden zu RepositoryError. Ein unerwarteter Bug
            # (TypeError/AttributeError) propagiert ROH -> wird im Scheduler als logger.exception
            # (mit Traceback) sichtbar, nicht als routinemaessiger DB-Fehler maskiert. Der
            # Fail-safe-Re-Arm passiert eine Ebene hoeher (AlarmGenerator.verarbeite faengt
            # breit): Service = Fail-safe-Aktion, Repo = Fehler-Klassifikation (Layer-Trennung).
            raise RepositoryError("Alarm konnte nicht gespeichert werden") from exc
        if not row_id:
            # Keine gueltige AUTO_INCREMENT-ID: None ODER 0 (AUTO_INCREMENT beginnt bei 1,
            # eine 0 signalisiert einen anomalen Schreibpfad). Fail-safe als Domaenenfehler
            # statt eine ungueltige ID als Erfolg zurueckzugeben.
            raise RepositoryError("Alarm wurde ohne gueltige ID gespeichert")
        return int(row_id)

    def get_alarms(self, state: AlarmState | None = None, limit: int = 100) -> list[Alarm]:
        _require_positive_limit(limit)
        if state is None:
            sql = _SELECT_OPEN_SQL
            params: tuple = (*(open_state.value for open_state in _OPEN_STATES), limit)
        else:
            sql = _SELECT_BY_STATE_SQL
            params = (state.value, limit)
        try:
            # get_connection() liefert eine DictCursor-Verbindung (database.py) -> rows = Dicts.
            with get_connection(self._config) as conn, conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            return [self._row_to_alarm(row) for row in rows]
        except (DatabaseConnectionError, DatabaseConfigError, pymysql.Error) as exc:
            # DB-Ausfall -> fail-safe (NF-01): nie roher Treiberfehler an den Endpoint.
            raise RepositoryError("Alarme konnten nicht gelesen werden") from exc
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            # Row-Mapping-Drift (ungueltiger Enum-Wert, fehlende Spalte, Schema-Drift nach
            # Migration). Pydantics ValidationError IST eine ValueError-Subklasse -> mit
            # gefangen. Serverseitiger Drift -> fail-safe RepositoryError, kein roher 500.
            raise RepositoryError("Alarme konnten nicht gelesen werden (Mapping-Drift)") from exc

    @staticmethod
    def _row_to_alarm(row: dict[str, Any]) -> Alarm:
        raised_at = row["raised_at"]
        if raised_at.tzinfo is None:
            # DB speichert UTC zeitzonenlos -> tzinfo nachziehen (analog Reading/Assessment).
            raised_at = raised_at.replace(tzinfo=UTC)
        # severity/state als String -> Pydantic validiert gegen die Enums (faengt Drift).
        return Alarm(
            id=row["id"],
            assessment_id=row["assessment_id"],
            severity=row["severity"],
            raised_at=raised_at,
            state=row["state"],
        )
