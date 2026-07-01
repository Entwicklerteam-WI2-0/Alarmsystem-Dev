"""DTB-57: Retention/Rotation der reading-Tabelle (SD-Karten-Schutz, Backend-Konzept Sec. 6a).

Loescht alte Roh-Messwerte (`reading`) nach N Tagen, damit die Dauerschreiblast die
SD-Karte des Raspberry Pi nicht unnoetig verschleisst. Bewusst NUR `reading`:
audit_log/acknowledgement bleiben voellig unberuehrt (NF-09 append-only). assessment-
Snapshots bleiben inhaltlich erhalten; lediglich `assessment.reading_id` wird per
`ON DELETE SET NULL` (schema.sql) auf NULL gesetzt — gewollt, da der Snapshot self-contained
und audit-fest ist (DTB-12). reading ist der Mengentreiber (~2.880 Zeilen/Tag/Sensor).

Sicherungen gegen versehentliches Leeren der falschen DB:
- Default = **Dry-Run**: zaehlt nur, loescht nichts. Echtes Loeschen erst mit --apply.
- --apply verlangt zusaetzlich --confirm <DB-NAME>, der exakt zur konfigurierten
  Ziel-DB (DB_NAME aus der Env) passen muss (bewusster, getippter Bestaetigungsschritt).
- Geloescht wird in Batches (--batch-limit), damit kein langer Tabellen-Lock entsteht.

Kein Produktionscode (laeuft nicht in der App), sondern ein Wartungsskript: per
systemd-Timer/cron als dedizierter Wartungs-User mit DELETE-Recht NUR auf `reading`
ausgefuehrt. Der App-User `alarm` bleibt append-only (grants.sql). Details: Pi-Setup.md.

Verbindungsparameter kommen wie ueberall aus den DB_*-Umgebungsvariablen (NF-07).

Beispiele:
    # Trockenlauf (zeigt nur, wie viele Zeilen aelter als 30 Tage sind):
    python -m tools.purge_readings --days 30
    # Echtes Loeschen (Bestaetigung der Ziel-DB Pflicht):
    python -m tools.purge_readings --days 30 --apply --confirm alarmsystem
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pymysql import Error as PyMySQLError

from src.storage.database import (
    DatabaseConfigError,
    DatabaseConnectionError,
    get_connection,
    load_database_config_from_env,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 30
DEFAULT_BATCH_LIMIT = 5000

_COUNT_SQL = "SELECT COUNT(*) AS n FROM reading WHERE measured_at < %s"
_DELETE_SQL = "DELETE FROM reading WHERE measured_at < %s LIMIT %s"


class PurgeError(Exception):
    """Fachlicher Abbruch der Retention (z. B. fehlende/falsche Ziel-DB-Bestaetigung)."""


def _utc_now() -> datetime:
    """Aktuelle Zeit in UTC (eigene Funktion, damit Tests sie monkeypatchen koennen)."""
    return datetime.now(UTC)


def compute_cutoff(now: datetime, days: int) -> datetime:
    """Stichzeitpunkt: alles strikt vor (now - days) ist 'alt'.

    now muss zeitzonenbewusst sein. Ein Nicht-UTC-Offset wird nach UTC konvertiert: reading.
    measured_at ist UTC, und PyMySQL sendet beim Escapen nur die Wall-Clock-Zeit (ohne tzinfo)
    — ohne Konvertierung waere der Vergleich um den Offset verschoben.
    """
    if now.tzinfo is None:
        raise ValueError("now muss zeitzonenbewusst (UTC) sein — reading.measured_at ist UTC")
    return now.astimezone(UTC) - timedelta(days=days)


def ensure_confirmed(target_db: str, confirm: str | None) -> None:
    """Schutz vor falscher DB: --confirm muss exakt dem konfigurierten DB-Namen entsprechen."""
    if confirm != target_db:
        raise PurgeError(
            f"--confirm '{confirm}' passt nicht zur Ziel-Datenbank '{target_db}'. "
            f"Zum echten Loeschen --confirm {target_db} angeben."
        )


def count_readings_before(conn: object, cutoff: datetime) -> int:
    """Zaehlt reading-Zeilen aelter als cutoff (Dry-Run-Basis, kein Schreibzugriff)."""
    try:
        with conn.cursor() as cursor:  # type: ignore[attr-defined]
            cursor.execute(_COUNT_SQL, (cutoff,))
            row = cursor.fetchone()
    except PyMySQLError as exc:
        # Treiberfehler in eine treiberunabhaengige Exception wrappen, damit main()
        # einen sauberen Exit-Code liefert statt eines rohen Tracebacks (Repository-Muster).
        raise DatabaseConnectionError("COUNT auf reading fehlgeschlagen") from exc
    return int(row["n"])


def delete_readings_before(conn: object, cutoff: datetime, batch_limit: int) -> int:
    """Loescht reading-Zeilen aelter als cutoff in Batches; committet pro Batch.

    Batch-weises Loeschen + Commit haelt den Tabellen-Lock kurz (wichtig auf dem Pi,
    wo der Scheduler parallel weiter INSERTet). Gibt die Gesamtzahl geloeschter Zeilen
    zurueck. Schleife endet, sobald ein Batch weniger als batch_limit Zeilen trifft.

    Treiberfehler (z. B. ERROR 1142, wenn das Skript versehentlich mit dem append-only
    App-User `alarm` statt dem Wartungs-User laeuft) werden in DatabaseConnectionError
    gewrappt -> sauberer Exit-Code 1 in main(), kein roher Traceback.
    """
    total = 0
    try:
        while True:
            with conn.cursor() as cursor:  # type: ignore[attr-defined]
                affected = cursor.execute(_DELETE_SQL, (cutoff, batch_limit))
            conn.commit()  # type: ignore[attr-defined]
            total += affected
            if affected < batch_limit:
                break
    except PyMySQLError as exc:
        raise DatabaseConnectionError(
            "DELETE auf reading fehlgeschlagen (fehlt das DELETE-Recht? Skript mit dem "
            "Wartungs-User 'alarm_maint' ausfuehren, s. Pi-Setup §11b)"
        ) from exc
    return total


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"muss > 0 sein, erhalten: {value}")
    return value


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parst die CLI-Argumente. Default ist bewusst Dry-Run (kein --apply)."""
    parser = argparse.ArgumentParser(
        prog="purge_readings",
        description="Loescht alte reading-Zeilen (Retention, SD-Karten-Schutz, DTB-57).",
    )
    parser.add_argument(
        "--days",
        type=_positive_int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Aufbewahrungsdauer in Tagen (Default: {DEFAULT_RETENTION_DAYS}).",
    )
    parser.add_argument(
        "--batch-limit",
        type=_positive_int,
        default=DEFAULT_BATCH_LIMIT,
        help=f"Zeilen pro DELETE-Batch (Default: {DEFAULT_BATCH_LIMIT}).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Tatsaechlich loeschen. Ohne dieses Flag nur Dry-Run (zaehlt, loescht nicht).",
    )
    parser.add_argument(
        "--confirm",
        metavar="DB_NAME",
        default=None,
        help="Name der Ziel-DB; muss bei --apply exakt DB_NAME entsprechen (Schutz).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Einstiegspunkt: Dry-Run zaehlt, --apply loescht. Gibt Exit-Code zurueck."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)

    try:
        config = load_database_config_from_env()
    except DatabaseConfigError as exc:
        logger.error("DB-Konfiguration unvollstaendig/ungueltig: %s", exc)
        return 2

    cutoff = compute_cutoff(_utc_now(), args.days)

    try:
        if not args.apply:
            with get_connection(config) as conn:
                count = count_readings_before(conn, cutoff)
            logger.info(
                "[DRY-RUN] %d reading-Zeilen aelter als %d Tage (vor %s UTC) wuerden "
                "geloescht. Zum echten Loeschen: --apply --confirm %s",
                count,
                args.days,
                cutoff.isoformat(),
                config.name,
            )
            return 0

        ensure_confirmed(config.name, args.confirm)
        with get_connection(config) as conn:
            deleted = delete_readings_before(conn, cutoff, args.batch_limit)
        logger.info(
            "%d reading-Zeilen aelter als %d Tage (vor %s UTC) aus '%s' geloescht.",
            deleted,
            args.days,
            cutoff.isoformat(),
            config.name,
        )
        return 0
    except PurgeError as exc:
        logger.error("Abbruch: %s", exc)
        return 2
    except DatabaseConnectionError as exc:
        logger.error("DB-Verbindung/Operation fehlgeschlagen: %s", exc)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
