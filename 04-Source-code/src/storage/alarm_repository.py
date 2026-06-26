"""Persistenz fuer ausgeloeste Alarme (DTB-27).

Speichert einen neu ausgeloesten Alarm (state='active') in MariaDB/MySQL via rohem
PyMySQL und parametrisiertem INSERT (E-35, Injection-Schutz). Bewusst minimal: nur
`save`. Lesepfade (DTB-31 GET /v1/alarms) und Zustandswechsel (DTB-24 ack/clear, RB-01
manuell) sind eigene Tickets und hier NICHT enthalten (kein UPDATE/DELETE-Pfad).

RB-01: Das Repository persistiert nur — es fuehrt keine Aktor-/Steuer-Aktion aus.
Muster wie src/storage/audit_repository.py.
"""

from abc import ABC, abstractmethod

import pymysql

from src.model.enums import AlarmState
from src.model.schemas import Alarm
from src.storage.database import (
    DatabaseConfig,
    DatabaseConfigError,
    DatabaseConnectionError,
    transaction,
)
from src.storage.repository import RepositoryError

# Spaltenreihenfolge des INSERT -- entspricht migrations/schema.sql (alarm).
# id ist AUTO_INCREMENT und wird NICHT gesetzt; assessment_id..state parametrisiert.
_INSERT_SQL = (
    "INSERT INTO alarm (assessment_id, severity, raised_at, state) VALUES (%s, %s, %s, %s)"
)


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


class AlarmRepository(ABC):
    """Abstrakte Persistenz fuer ausgeloeste Alarme. Bewusst minimal: nur `save`."""

    @abstractmethod
    def save(self, alarm: Alarm) -> int:
        """Speichert einen ausgeloesten Alarm und gibt die vergebene ID zurueck."""
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

    def all(self) -> list[Alarm]:
        """Liest alle Alarme in Einfuege-Reihenfolge (nur Double; YAGNI-Lesepfad).

        Gibt Kopien zurueck, damit der interne Stand nicht ueber die zurueckgegebenen
        (mutablen) Alarm-Objekte veraendert werden kann (Lese-Aliasing vermeiden).
        """
        return [alarm.model_copy() for alarm in self._alarms]


class MySqlAlarmRepository(AlarmRepository):
    """Alarm-Persistenz auf MariaDB/MySQL via rohem PyMySQL (DTB-27, E-35).

    Schreibt ausschliesslich per parametrisiertem INSERT (Injection-Schutz, nie
    String-Formatierung). Kein UPDATE-/DELETE-Pfad (Zustandswechsel = DTB-24/manuell).
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
