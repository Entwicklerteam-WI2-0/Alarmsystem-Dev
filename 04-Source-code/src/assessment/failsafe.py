"""Fail-safe-Logik fuer Stale-Daten und DB-Ausfall (DTB-13).

Die Stale-Erkennung bleibt DB-agnostisch: sie arbeitet gegen das Repository-Interface
(get_latest, DTB-28) und vergleicht Zeitstempel ausschliesslich in UTC. MySQL-spezifische
Details (DATETIME(3), zeitzenlos) werden in der Persistenzschicht behandelt.

Bezug: NF-01; E-34; DTB-12; Schwellenwerte.md §3.
"""

from datetime import datetime, timedelta

from src.model.enums import RiskLevel
from src.model.schemas import Assessment, Reading


def is_stale(reading: Reading | None, now: datetime, timeout_s: float) -> bool:
    """Prueft, ob ein Reading als veraltet gilt.

    Args:
        reading: Das zu pruefende Reading. None gilt als veraltet (noch keine Daten).
        now: Referenzzeitpunkt (UTC), gegen den gemessen wird.
        timeout_s: Maximal erlaubtes Alter in Sekunden (kommt aus thresholds.json).

    Returns:
        True, wenn das Reading aelter als timeout_s ist oder fehlt.
    """
    if reading is None:
        return True
    age = now - reading.measured_at
    return age > timedelta(seconds=timeout_s)


def build_unknown_assessment(reason: str, ts: datetime) -> Assessment:
    """Baut einen fail-safe Assessment mit risk_level=unknown.

    Wird fuer zwei getrennte Faelle verwendet:
    - Stale-Daten (DTB-13): letztes Reading zu alt.
    - DB-Ausfall: Repository.get_latest() wirft RepositoryError.

    Args:
        reason: Menschenlesbare Begruendung fuer Audit/Log.
        ts: Zeitstempel der Bewertung (UTC).

    Returns:
        Assessment mit risk_level=RiskLevel.UNKNOWN.
    """
    return Assessment(
        ts=ts,
        risk_level=RiskLevel.UNKNOWN,
        explanation=f"Fail-safe: {reason}",
    )
