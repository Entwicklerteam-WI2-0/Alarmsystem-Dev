"""Fail-safe-Logik fuer Stale-Daten, Plausibilitaet und DB-Ausfall (DTB-13).

Die Logik bleibt DB-agnostisch: sie arbeitet gegen das Repository-Interface
(get_latest, DTB-28) und vergleicht Zeitstempel ausschliesslich in UTC. MySQL-spezifische
Details (DATETIME(3), zeitzenlos) werden in der Persistenzschicht behandelt.

Bezug: NF-01; E-34; DTB-12; Schwellenwerte.md §3.
"""

from datetime import datetime, timedelta

from src.config.loader import DatenqualitaetSchwellen
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


def check_plausibility(
    current: Reading,
    previous: Reading | None,
    thresholds: DatenqualitaetSchwellen,
) -> str | None:
    """Prueft ein Reading auf physikalische Plausibilitaet gegen ein vorheriges.

    Prueft zwei laut Schwellenwerte.md §3 definierte Fehlerbilder:
    - Sprung: Aenderung der Oberflaechentemperatur > 5 °C/min.
    - Flatline: Keine Aenderung der Oberflaechentemperatur ueber >= 15 min
      (innerhalb einer Toleranz fuer Sensorrauschen).

    Args:
        current: Aktuelles Reading.
        previous: Vorheriges Reading desselben Sensors. Bei None kann keine
            Sprung-/Flatline-Pruefung stattfinden -> plausibel.
        thresholds: Parametrierbare Grenzwerte fuer Datenqualitaet.

    Returns:
        Menschenlesbarer Grund, wenn unplausibel; sonst None.
    """
    if previous is None:
        return None

    delta_t = current.measured_at - previous.measured_at
    delta_min = delta_t.total_seconds() / 60.0
    if delta_min <= 0:
        # Negativer oder gleicher Zeitstempel ist ein Datenfehler -> unplausibel.
        return "invalid timestamp order"

    delta_temp_c = current.surface_temp_c - previous.surface_temp_c
    jump_rate = abs(delta_temp_c) / delta_min
    if jump_rate > thresholds.max_temp_jump_c_per_min:
        return f"temperature jump {jump_rate:.2f} C/min exceeds limit"

    if delta_min >= thresholds.flatline_timeout_min:
        if abs(delta_temp_c) <= thresholds.flatline_epsilon_c:
            return "temperature flatline"

    return None


def build_unknown_assessment(reason: str, ts: datetime) -> Assessment:
    """Baut einen fail-safe Assessment mit risk_level=unknown.

    Wird fuer getrennte Fail-safe-Faelle verwendet:
    - Stale-Daten (DTB-13): letztes Reading zu alt.
    - DB-Ausfall: Repository.get_latest() wirft RepositoryError.
    - Unplausible Daten: Sprung oder Flatline.

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
