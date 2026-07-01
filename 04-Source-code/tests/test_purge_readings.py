"""Tests fuer das Retention-Wartungsskript tools/purge_readings.py (DTB-57).

Zwei Ebenen:
- DB-frei (laeuft immer, auch in der DB-freien CI): Cutoff-Berechnung, Ziel-DB-Guard,
  Batch-Loesch-Schleife und main()-Verdrahtung gegen eine Fake-Connection.
- Integration (skippt ohne erreichbare MariaDB): echtes Loeschen nur alter reading-Zeilen,
  Dry-Run laesst alles stehen, fehlender/falscher --confirm bricht ab.

Das Skript fasst ausschliesslich `reading` an (SD-Karten-Schutz, Backend-Konzept Sec. 6a);
audit_log/assessment bleiben unberuehrt (NF-09 append-only).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone

import pymysql
import pytest

from tools import purge_readings


# --------------------------------------------------------------------------- #
# DB-freie Fakes
# --------------------------------------------------------------------------- #
class _FakeCursor:
    """Minimaler DB-API-Cursor: programmierte execute()-Rueckgaben + SQL-Mitschnitt."""

    def __init__(self, owner: _FakeConnection) -> None:
        self._owner = owner

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple = ()) -> int:
        self._owner.executed.append((sql, params))
        up = sql.upper()
        if self._owner.error is not None and self._owner.error_on in up:
            raise self._owner.error
        if "DELETE" in up:
            return self._owner.delete_batches.pop(0)
        return 0

    def fetchone(self) -> dict[str, int]:
        return {"n": self._owner.count_value}


class _FakeConnection:
    def __init__(
        self,
        count_value: int = 0,
        delete_batches: list[int] | None = None,
        error: Exception | None = None,
        error_on: str = "",
    ) -> None:
        self.count_value = count_value
        self.delete_batches = list(delete_batches or [])
        self.executed: list[tuple[str, tuple]] = []
        self.commits = 0
        self.closed = False
        # Optionaler Treiberfehler: error wird geworfen, sobald error_on (z. B. "DELETE"
        # oder "COUNT") im SQL vorkommt -> simuliert ERROR 1142 / Lock-Timeout etc.
        self.error = error
        self.error_on = error_on

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        # Modelliert, dass get_connection() die Verbindung beim Verlassen schliesst -> ein
        # Bypass des Contextmanagers in main() (Connection-Leak) wuerde im Test auffallen.
        self.closed = True


@contextmanager
def _connection_cm(conn: _FakeConnection):
    """Spiegelt get_connection(): yield + garantiertes close() im finally (auch bei Fehler)."""
    try:
        yield conn
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# compute_cutoff
# --------------------------------------------------------------------------- #
def test_compute_cutoff_subtracts_days_in_utc():
    now = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)

    cutoff = purge_readings.compute_cutoff(now, 30)

    assert cutoff == datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
    assert cutoff.tzinfo == UTC


def test_compute_cutoff_rejects_naive_now():
    naive = datetime(2026, 6, 29, 12, 0, 0)  # noqa: DTZ001 (bewusst tz-naiv fuer den Test)

    with pytest.raises(ValueError, match="UTC"):
        purge_readings.compute_cutoff(naive, 30)


def test_compute_cutoff_converts_non_utc_offset_to_utc():
    # 14:00 +02:00 == 12:00 UTC. Ohne Konvertierung waere der Cutoff um 2 h verschoben
    # und der Vergleich gegen die UTC-gespeicherten measured_at falsch.
    plus_two = datetime(2026, 6, 29, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    cutoff = purge_readings.compute_cutoff(plus_two, 30)

    assert cutoff == datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
    assert cutoff.tzinfo == UTC


# --------------------------------------------------------------------------- #
# Ziel-DB-Guard
# --------------------------------------------------------------------------- #
def test_ensure_confirmed_passes_on_exact_match():
    # Kein Fehler -> stiller Durchlauf.
    purge_readings.ensure_confirmed("alarmsystem", "alarmsystem")


def test_ensure_confirmed_raises_on_mismatch():
    with pytest.raises(purge_readings.PurgeError, match="confirm"):
        purge_readings.ensure_confirmed("alarmsystem", "alarmsystem_dev")


def test_ensure_confirmed_raises_when_confirm_missing():
    with pytest.raises(purge_readings.PurgeError, match="confirm"):
        purge_readings.ensure_confirmed("alarmsystem", None)


# --------------------------------------------------------------------------- #
# count / delete (Fake-Connection)
# --------------------------------------------------------------------------- #
def test_count_readings_before_returns_count():
    conn = _FakeConnection(count_value=7)
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)

    assert purge_readings.count_readings_before(conn, cutoff) == 7
    assert "SELECT COUNT(*)" in conn.executed[0][0]


def test_delete_readings_before_batches_until_drained():
    # 12 alte Zeilen, batch_limit 5 -> 5, 5, 2 (letzter Batch < limit -> Stopp).
    conn = _FakeConnection(delete_batches=[5, 5, 2])
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)

    deleted = purge_readings.delete_readings_before(conn, cutoff, batch_limit=5)

    assert deleted == 12
    delete_calls = [e for e in conn.executed if "DELETE" in e[0].upper()]
    assert len(delete_calls) == 3
    assert conn.commits == 3  # pro Batch committen, damit der Lock nicht waechst


def test_delete_readings_before_stops_immediately_when_nothing_old():
    conn = _FakeConnection(delete_batches=[0])
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)

    deleted = purge_readings.delete_readings_before(conn, cutoff, batch_limit=5)

    assert deleted == 0
    assert len([e for e in conn.executed if "DELETE" in e[0].upper()]) == 1


def test_delete_readings_before_exact_multiple_runs_one_empty_extra_batch():
    # Genau batch_limit alte Zeilen -> erster Batch == limit (Schleife laeuft weiter),
    # zweiter Batch trifft 0 (< limit -> Stopp). Ergebnis korrekt, eine Leerrunde.
    conn = _FakeConnection(delete_batches=[5, 0])
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)

    deleted = purge_readings.delete_readings_before(conn, cutoff, batch_limit=5)

    assert deleted == 5
    assert len([e for e in conn.executed if "DELETE" in e[0].upper()]) == 2


def test_count_readings_before_wraps_driver_error():
    conn = _FakeConnection(error=pymysql.err.OperationalError(1142, "denied"), error_on="COUNT")
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)

    # Treiberfehler -> treiberunabhaengige Exception (kein roher pymysql-Fehler nach oben).
    with pytest.raises(purge_readings.DatabaseConnectionError):
        purge_readings.count_readings_before(conn, cutoff)


def test_delete_readings_before_wraps_driver_error_with_maint_hint():
    conn = _FakeConnection(
        delete_batches=[], error=pymysql.err.OperationalError(1142, "denied"), error_on="DELETE"
    )
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)

    with pytest.raises(purge_readings.DatabaseConnectionError, match="alarm_maint"):
        purge_readings.delete_readings_before(conn, cutoff, batch_limit=5)


# --------------------------------------------------------------------------- #
# Argument-Parsing
# --------------------------------------------------------------------------- #
def test_parse_args_defaults_to_dry_run():
    args = purge_readings.parse_args([])

    assert args.apply is False  # Default = Dry-Run, loescht nie versehentlich
    assert args.days == purge_readings.DEFAULT_RETENTION_DAYS
    assert args.batch_limit == purge_readings.DEFAULT_BATCH_LIMIT


def test_parse_args_rejects_non_positive_days():
    with pytest.raises(SystemExit):
        purge_readings.parse_args(["--days", "0"])


# --------------------------------------------------------------------------- #
# main()-Verdrahtung gegen Fake-Connection (DB-frei)
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch) -> _FakeConnection:
    """Verdrahtet main() auf eine Fake-Connection + feste Config (kein echtes DB-Env noetig)."""
    conn = _FakeConnection(count_value=3, delete_batches=[3, 0])

    class _Cfg:
        name = "alarmsystem"

    def _fake_get_connection(config: object = None):  # noqa: ARG001
        return _connection_cm(conn)

    monkeypatch.setattr(purge_readings, "load_database_config_from_env", lambda: _Cfg())
    monkeypatch.setattr(purge_readings, "get_connection", _fake_get_connection)
    return conn


def test_main_dry_run_counts_but_does_not_delete(fake_env: _FakeConnection):
    rc = purge_readings.main(["--days", "30"])

    assert rc == 0
    assert all("DELETE" not in sql.upper() for sql, _ in fake_env.executed)
    assert fake_env.closed  # Verbindung sauber geschlossen (kein Leak)


def test_main_apply_with_matching_confirm_deletes(fake_env: _FakeConnection):
    rc = purge_readings.main(["--days", "30", "--apply", "--confirm", "alarmsystem"])

    assert rc == 0
    assert any("DELETE" in sql.upper() for sql, _ in fake_env.executed)
    assert fake_env.closed  # Verbindung sauber geschlossen (kein Leak)


def test_main_apply_without_confirm_aborts_without_delete(fake_env: _FakeConnection):
    rc = purge_readings.main(["--days", "30", "--apply"])

    assert rc != 0
    assert all("DELETE" not in sql.upper() for sql, _ in fake_env.executed)


def test_main_returns_2_on_db_config_error(monkeypatch: pytest.MonkeyPatch):
    def _raise() -> object:
        raise purge_readings.DatabaseConfigError("DB_PASSWORD fehlt")

    monkeypatch.setattr(purge_readings, "load_database_config_from_env", _raise)

    assert purge_readings.main(["--days", "30"]) == 2  # sauberer Abbruch, kein Crash


def test_main_returns_1_on_db_connection_error(monkeypatch: pytest.MonkeyPatch):
    class _Cfg:
        name = "alarmsystem"

    def _raise_conn(config: object = None):  # noqa: ARG001
        raise purge_readings.DatabaseConnectionError("DB nicht erreichbar")

    monkeypatch.setattr(purge_readings, "load_database_config_from_env", lambda: _Cfg())
    monkeypatch.setattr(purge_readings, "get_connection", _raise_conn)

    assert purge_readings.main(["--days", "30"]) == 1  # Fail-safe: nicht-null Exit-Code


def test_main_apply_returns_1_on_delete_driver_error(monkeypatch: pytest.MonkeyPatch):
    # Realistischer Trigger: Lauf als App-User 'alarm' (kein DELETE) -> ERROR 1142.
    # Erwartung: sauberer Exit-Code 1, KEIN roher Traceback (Befund F2/HIGH-1).
    conn = _FakeConnection(
        delete_batches=[], error=pymysql.err.OperationalError(1142, "denied"), error_on="DELETE"
    )

    class _Cfg:
        name = "alarmsystem"

    def _get(config: object = None):  # noqa: ARG001
        return _connection_cm(conn)

    monkeypatch.setattr(purge_readings, "load_database_config_from_env", lambda: _Cfg())
    monkeypatch.setattr(purge_readings, "get_connection", _get)

    assert purge_readings.main(["--days", "30", "--apply", "--confirm", "alarmsystem"]) == 1
    assert conn.closed  # auch im Fehlerpfad wird die Verbindung geschlossen


def test_main_apply_passes_batch_limit_to_delete(fake_env: _FakeConnection):
    rc = purge_readings.main(
        ["--days", "30", "--apply", "--confirm", "alarmsystem", "--batch-limit", "7"]
    )

    assert rc == 0
    delete_params = [params for sql, params in fake_env.executed if "DELETE" in sql.upper()]
    assert delete_params and delete_params[0][1] == 7  # CLI-Wert erreicht die DELETE-Query


# --------------------------------------------------------------------------- #
# Integration (echte MariaDB) — skippt ohne DB
# --------------------------------------------------------------------------- #
_NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=UTC)


def _insert_reading(cursor: object, sensor_id: str, measured_at: datetime) -> None:
    cursor.execute(  # type: ignore[attr-defined]
        "INSERT INTO reading "
        "(sensor_id, measured_at, received_at, surface_temp_c, air_temp_c, humidity_pct) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (sensor_id, measured_at, measured_at, 1.0, 2.0, 80.0),
    )


@pytest.fixture
def seeded_db(database: str):
    """Leert reading und legt 2 alte (45/46 Tage) + 2 frische (1/2 Tage) Zeilen an."""
    from tests._db_helpers import conn_params

    conn = pymysql.connect(**conn_params(database=database, autocommit=False))
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM reading")
            for offset in (45, 46):
                _insert_reading(cursor, "anr-rwy-01", _NOW - timedelta(days=offset))
            for offset in (1, 2):
                _insert_reading(cursor, "anr-rwy-01", _NOW - timedelta(days=offset))
        conn.commit()
    finally:
        conn.close()
    return database


def _reading_count(database: str) -> int:
    from tests._db_helpers import conn_params

    conn = pymysql.connect(**conn_params(database=database, autocommit=True))
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM reading")
            return int(cursor.fetchone()["n"])
    finally:
        conn.close()


def test_integration_dry_run_keeps_all_rows(seeded_db: str, monkeypatch: pytest.MonkeyPatch):
    from tests._db_helpers import db_config_for

    monkeypatch.setattr(
        purge_readings, "load_database_config_from_env", lambda: db_config_for(seeded_db)
    )
    monkeypatch.setattr(purge_readings, "_utc_now", lambda: _NOW)

    rc = purge_readings.main(["--days", "30"])

    assert rc == 0
    assert _reading_count(seeded_db) == 4  # Dry-Run loescht nichts


def test_integration_apply_deletes_only_old_rows(seeded_db: str, monkeypatch: pytest.MonkeyPatch):
    from tests._db_helpers import db_config_for

    monkeypatch.setattr(
        purge_readings, "load_database_config_from_env", lambda: db_config_for(seeded_db)
    )
    monkeypatch.setattr(purge_readings, "_utc_now", lambda: _NOW)

    rc = purge_readings.main(["--days", "30", "--apply", "--confirm", seeded_db])

    assert rc == 0
    assert _reading_count(seeded_db) == 2  # nur die 2 frischen bleiben


def test_integration_apply_nulls_assessment_reading_id_but_keeps_snapshot(
    seeded_db: str, monkeypatch: pytest.MonkeyPatch
):
    """FK-Falle (Befund F3): assessment.reading_id -> reading(id) ON DELETE SET NULL.

    Beweist gegen eine echte DB: Loeschen einer referenzierten alten reading (a) scheitert
    NICHT am FK, (b) loescht die reading, (c) laesst die assessment-Zeile leben, (d) nullt nur
    deren reading_id. Belegt die Docstring-/Doku-Aussage gegen MariaDB.
    """
    from tests._db_helpers import conn_params, db_config_for

    conn = pymysql.connect(**conn_params(database=seeded_db, autocommit=False))
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM assessment")
            cursor.execute("DELETE FROM reading")
            old = _NOW - timedelta(days=45)
            _insert_reading(cursor, "anr-rwy-01", old)
            old_reading_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO assessment (ts, reading_id, risk_level) VALUES (%s, %s, %s)",
                (old, old_reading_id, "green"),
            )
            assessment_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        purge_readings, "load_database_config_from_env", lambda: db_config_for(seeded_db)
    )
    monkeypatch.setattr(purge_readings, "_utc_now", lambda: _NOW)

    assert purge_readings.main(["--days", "30", "--apply", "--confirm", seeded_db]) == 0

    conn = pymysql.connect(**conn_params(database=seeded_db, autocommit=True))
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM reading WHERE id = %s", (old_reading_id,))
            assert cursor.fetchone()["n"] == 0  # alte reading geloescht
            cursor.execute("SELECT reading_id FROM assessment WHERE id = %s", (assessment_id,))
            row = cursor.fetchone()
            assert row is not None  # assessment-Snapshot lebt weiter
            assert row["reading_id"] is None  # nur der Link genullt (ON DELETE SET NULL)
    finally:
        conn.close()
