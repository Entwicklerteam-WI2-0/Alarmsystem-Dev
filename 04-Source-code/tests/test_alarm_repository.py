"""Tests fuer das Alarm-Persistenz-Repository (DTB-27).

DB-freier Kern: InMemory-Double + MySQL-Variante mit gemocktem `transaction`.
Echte MariaDB-Integrationstests (FK-/CHECK-Verletzung, Roundtrip) folgen nach
DTB-21 (geteilte conftest-Fixtures). Muster wie tests/test_audit_repository.py.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pymysql
import pytest

from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm
from src.storage.alarm_repository import (
    AlarmRepository,
    InMemoryAlarmRepository,
    MySqlAlarmRepository,
)
from src.storage.database import DatabaseConfigError, DatabaseConnectionError
from src.storage.repository import RepositoryError

UTC_NOW = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


def _alarm(**overrides) -> Alarm:
    base = dict(
        assessment_id=1,
        severity=AlarmSeverity.WARNING,
        raised_at=UTC_NOW,
    )
    base.update(overrides)
    return Alarm(**base)


def _mock_transaction():
    """Baut (tx, cursor) fuer `with transaction() as conn, conn.cursor() as cur`."""
    cursor = MagicMock()
    cursor.lastrowid = 1
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    tx = MagicMock()
    tx.__enter__.return_value = conn
    return tx, cursor


# --- InMemory-Double (T1) ---


def test_inmemory_save_returns_generated_id():
    repo = InMemoryAlarmRepository()
    assert repo.save(_alarm()) == 1


def test_inmemory_save_increments_id():
    repo = InMemoryAlarmRepository()
    repo.save(_alarm())
    assert repo.save(_alarm()) == 2


def test_inmemory_saved_alarm_is_readable_and_active():
    repo = InMemoryAlarmRepository()
    repo.save(_alarm(severity=AlarmSeverity.CRITICAL))
    gespeichert = repo.all()
    assert len(gespeichert) == 1
    assert gespeichert[0].id == 1
    assert gespeichert[0].severity is AlarmSeverity.CRITICAL
    assert gespeichert[0].state is AlarmState.ACTIVE  # ausgeloeste Alarme sind aktiv (V8)


def test_inmemory_is_an_alarmrepository():
    assert isinstance(InMemoryAlarmRepository(), AlarmRepository)


def test_inmemory_all_gibt_kopien_zurueck():
    # Lese-Aliasing vermeiden: all() muss bei jedem Aufruf unabhaengige Kopien liefern, nicht
    # Referenzen auf den internen Stand. Pruefung ueber distinkte Instanzen statt In-Place-
    # Mutation -> robust, falls Alarm spaeter frozen=True wird (sonst ValidationError statt
    # aussagekraeftiger Assertion).
    repo = InMemoryAlarmRepository()
    repo.save(_alarm(severity=AlarmSeverity.WARNING))
    assert repo.all()[0] is not repo.all()[0]
    assert repo.all()[0].severity is AlarmSeverity.WARNING


# --- MySQL-Variante (T2/T3), transaction gemockt ---


def test_mysql_save_uses_parametrized_insert():
    tx, cursor = _mock_transaction()
    with patch("src.storage.alarm_repository.transaction", return_value=tx) as mock_tx:
        new_id = MySqlAlarmRepository().save(_alarm(severity=AlarmSeverity.CRITICAL))
    assert new_id == 1
    # commit-tragender Helper wirklich genutzt (nicht versehentlich get_connection ohne Commit)
    mock_tx.assert_called_once_with(None)
    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args[0]
    assert sql.strip().upper().startswith("INSERT INTO ALARM")
    # parametrisiert: Werte in params, NICHT im SQL-String (SQL-Injection-Schutz, V2)
    assert sql.count("%s") == 4
    assert "critical" not in sql
    # Spaltenreihenfolge im SQL UND exakte params -> faengt einen severity/state-Swap (V5)
    assert "assessment_id, severity, raised_at, state" in sql
    assert params == (1, "critical", UTC_NOW, "active")


def test_mysql_save_returns_lastrowid():
    tx, cursor = _mock_transaction()
    cursor.lastrowid = 42
    with patch("src.storage.alarm_repository.transaction", return_value=tx):
        assert MySqlAlarmRepository().save(_alarm()) == 42


@pytest.mark.parametrize("startup_error", [DatabaseConnectionError, DatabaseConfigError])
def test_mysql_save_wraps_startup_error_failsafe(startup_error):
    # Real wirft der Verbindungsaufbau erst beim __enter__ des transaction-Kontexts
    # (get_connection) -> genau diesen Eintrittspunkt nachbilden, nicht den Aufruf.
    tx, _cursor = _mock_transaction()
    tx.__enter__.side_effect = startup_error("Startup-Fehler")
    with patch("src.storage.alarm_repository.transaction", return_value=tx):
        with pytest.raises(RepositoryError):  # V4: nie roher Fehler, Alarm nicht still verloren
            MySqlAlarmRepository().save(_alarm())


def test_mysql_save_wraps_query_error_failsafe():
    # CHECK-/FK-Verletzung kommt als pymysql.Error aus cursor.execute (V9).
    tx, cursor = _mock_transaction()
    treiberfehler = pymysql.Error("CHECK/FK verletzt")
    cursor.execute.side_effect = treiberfehler
    with patch("src.storage.alarm_repository.transaction", return_value=tx):
        with pytest.raises(RepositoryError) as excinfo:
            MySqlAlarmRepository().save(_alarm())
    # Ursache bleibt erhalten (raise ... from exc) -- wichtig fuer Fail-safe-Diagnose.
    assert excinfo.value.__cause__ is treiberfehler


@pytest.mark.parametrize("kein_id", [None, 0])
def test_mysql_save_missing_or_zero_lastrowid_failsafe(kein_id):
    # V6: keine gueltige AUTO_INCREMENT-ID (None ODER 0 -- AUTO_INCREMENT beginnt bei 1)
    # -> RepositoryError statt eine anomale ID 0 als "Erfolg" zurueckzugeben.
    tx, cursor = _mock_transaction()
    cursor.lastrowid = kein_id
    with patch("src.storage.alarm_repository.transaction", return_value=tx):
        with pytest.raises(RepositoryError):
            MySqlAlarmRepository().save(_alarm())


def test_alarmrepository_has_no_mutation_path_rb01():
    # V3/V11 (RB-01): Das Interface kennt KEINEN Mutationspfad -- kein update/delete/clear/
    # acknowledge (kein Aktor, kein Auto-Zustandswechsel). Strukturell erzwungen. `get_alarms`
    # (DTB-31) ist ein reiner LESEpfad und damit RB-01-neutral (kein Mutationsverb).
    for verboten in ("update", "delete", "clear", "acknowledge", "remove"):
        assert not hasattr(AlarmRepository, verboten)
    assert AlarmRepository.__abstractmethods__ == frozenset({"save", "get_alarms"})


# --- V7 wird am Modell-Rand erzwungen (Alarm-Konstruktion), nicht im Repo ---


@pytest.mark.parametrize("repo_cls", [InMemoryAlarmRepository, MySqlAlarmRepository])
@pytest.mark.parametrize("zustand", [AlarmState.ACKNOWLEDGED, AlarmState.CLEARED])
def test_save_rejects_non_active_alarm(repo_cls, zustand):
    # V8: save() persistiert nur AUSGELOESTE (aktive) Alarme. Ein nicht-aktiver Zustand
    # ist ein Aufrufer-Fehler (Zustandswechsel laufen ueber DTB-24/manuell), kein DB-Write.
    # Frische Instanz pro Lauf (kein geteilter Test-State).
    with pytest.raises(ValueError):
        repo_cls().save(_alarm(state=zustand))


def test_naive_raised_at_rejected_at_model_boundary():
    from pydantic import ValidationError

    naive = datetime(2026, 6, 26, 12, 0)  # bewusst ohne tzinfo
    with pytest.raises(ValidationError):
        Alarm(assessment_id=1, severity=AlarmSeverity.WARNING, raised_at=naive)


# --- get_alarms: Lesepfad fuer GET /v1/alarms (DTB-31) -----------------------------


def _mock_get_connection(rows):
    """Baut (gc, cursor) fuer `with get_connection() as conn, conn.cursor() as cur`.

    cur.fetchall() liefert `rows` (DictCursor -> Liste von Dicts).
    """
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    gc = MagicMock()
    gc.__enter__.return_value = conn
    return gc, cursor


def _row(id_=1, assessment_id=1, severity="warning", raised_at=UTC_NOW, state="active"):
    return {
        "id": id_,
        "assessment_id": assessment_id,
        "severity": severity,
        "raised_at": raised_at,
        "state": state,
    }


# InMemory-Double


def test_inmemory_get_alarms_returns_active_newest_first():
    repo = InMemoryAlarmRepository()
    repo.save(_alarm(raised_at=datetime(2026, 6, 26, 10, 0, tzinfo=UTC)))  # id 1, aelter
    repo.save(_alarm(raised_at=datetime(2026, 6, 26, 12, 0, tzinfo=UTC)))  # id 2, neuer
    ids = [a.id for a in repo.get_alarms()]
    assert ids == [2, 1]  # newest-first (raised_at DESC) fuer den Resync


def test_inmemory_get_alarms_tie_break_by_id_desc():
    # Gleiche raised_at -> stabiler Tie-Break id DESC (matcht ORDER BY raised_at DESC, id DESC).
    repo = InMemoryAlarmRepository()
    same = datetime(2026, 6, 26, 12, 0, tzinfo=UTC)
    repo._alarms = [_alarm(id=1, raised_at=same), _alarm(id=2, raised_at=same)]
    assert [a.id for a in repo.get_alarms()] == [2, 1]


def test_inmemory_get_alarms_respects_limit():
    repo = InMemoryAlarmRepository()
    for _ in range(3):
        repo.save(_alarm())
    assert len(repo.get_alarms(limit=2)) == 2


def test_inmemory_get_alarms_returns_copies():
    repo = InMemoryAlarmRepository()
    repo.save(_alarm())
    assert repo.get_alarms()[0] is not repo.get_alarms()[0]


@pytest.mark.parametrize("bad_limit", [0, -1, 501])
def test_inmemory_get_alarms_limit_out_of_range(bad_limit):
    # Unter 1 ODER ueber der Obergrenze (500) -> ValueError am Repo-Rand (Defense-in-Depth).
    with pytest.raises(ValueError):
        InMemoryAlarmRepository().get_alarms(limit=bad_limit)


def test_inmemory_get_alarms_default_excludes_cleared():
    # White-box: das save-only-Double kann offiziell keine nicht-aktiven Alarme aufnehmen
    # (RB-01), daher den internen Stand bewusst seeden, um den OFFEN-Filter (active+
    # acknowledged, ohne cleared) der Default-Abfrage zu pruefen.
    repo = InMemoryAlarmRepository()
    repo._alarms = [
        _alarm(id=1, state=AlarmState.ACTIVE),
        _alarm(id=2, state=AlarmState.ACKNOWLEDGED),
        _alarm(id=3, state=AlarmState.CLEARED),
    ]
    states = {a.state for a in repo.get_alarms()}
    assert states == {AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED}


def test_inmemory_get_alarms_state_filter():
    repo = InMemoryAlarmRepository()
    repo._alarms = [
        _alarm(id=1, state=AlarmState.ACTIVE),
        _alarm(id=2, state=AlarmState.CLEARED),
    ]
    cleared = repo.get_alarms(state=AlarmState.CLEARED)
    assert [a.id for a in cleared] == [2]


# MySQL-Variante (get_connection gemockt)


def test_mysql_get_alarms_open_default_uses_in_clause():
    gc, cursor = _mock_get_connection([_row(id_=1), _row(id_=2, severity="critical")])
    with patch("src.storage.alarm_repository.get_connection", return_value=gc):
        alarms = MySqlAlarmRepository().get_alarms(limit=50)
    sql, params = cursor.execute.call_args[0]
    assert "FROM alarm" in sql
    # Ohne Filter: offene Alarme = active + acknowledged (IN-Klausel), cleared ausgeschlossen.
    assert "state IN (%s, %s)" in sql
    assert "ORDER BY raised_at DESC" in sql
    assert "id DESC" in sql  # stabiler Tie-Break muss erhalten bleiben (Sort-Invariante)
    assert params == ("active", "acknowledged", 50)
    assert [a.id for a in alarms] == [1, 2]
    assert alarms[1].severity is AlarmSeverity.CRITICAL


def test_mysql_get_alarms_state_filter_uses_equality():
    gc, cursor = _mock_get_connection([_row(state="cleared")])
    with patch("src.storage.alarm_repository.get_connection", return_value=gc):
        MySqlAlarmRepository().get_alarms(state=AlarmState.CLEARED, limit=10)
    sql, params = cursor.execute.call_args[0]
    assert "state = %s" in sql
    assert params == ("cleared", 10)


def test_mysql_get_alarms_maps_row_to_alarm():
    gc, _cursor = _mock_get_connection([_row(id_=9, assessment_id=4, severity="critical")])
    with patch("src.storage.alarm_repository.get_connection", return_value=gc):
        alarm = MySqlAlarmRepository().get_alarms()[0]
    assert alarm.id == 9
    assert alarm.assessment_id == 4
    assert alarm.severity is AlarmSeverity.CRITICAL
    assert alarm.state is AlarmState.ACTIVE


def test_mysql_get_alarms_naive_raised_at_becomes_utc():
    naive = datetime(2026, 6, 26, 12, 0)  # DB liefert zeitzonenlos
    gc, _cursor = _mock_get_connection([_row(raised_at=naive)])
    with patch("src.storage.alarm_repository.get_connection", return_value=gc):
        alarm = MySqlAlarmRepository().get_alarms()[0]
    assert alarm.raised_at.tzinfo is not None
    assert alarm.raised_at == naive.replace(tzinfo=UTC)


@pytest.mark.parametrize("db_error", [DatabaseConnectionError, DatabaseConfigError, pymysql.Error])
def test_mysql_get_alarms_wraps_db_error_failsafe(db_error):
    # Verbindungs-, Config- UND Treiberfehler werden alle zu RepositoryError (NF-01,
    # symmetrisch zum save-Pfad) -- nie roher Fehler an den Endpoint.
    gc, _cursor = _mock_get_connection([])
    gc.__enter__.side_effect = db_error("DB weg")
    with patch("src.storage.alarm_repository.get_connection", return_value=gc):
        with pytest.raises(RepositoryError):
            MySqlAlarmRepository().get_alarms()


@pytest.mark.parametrize("bad_limit", [0, -1, 501])
def test_mysql_get_alarms_limit_out_of_range(bad_limit):
    with pytest.raises(ValueError):
        MySqlAlarmRepository().get_alarms(limit=bad_limit)


def test_mysql_get_alarms_mapping_drift_failsafe():
    # Ungueltiger Enum-Wert aus der DB (Schema-/Migrationsdrift) -> Pydantic-ValidationError
    # beim Mapping. Muss fail-safe als RepositoryError aufschlagen (NF-01), nie roh als 500.
    gc, _cursor = _mock_get_connection([_row(severity="bogus")])
    with patch("src.storage.alarm_repository.get_connection", return_value=gc):
        with pytest.raises(RepositoryError):
            MySqlAlarmRepository().get_alarms()
