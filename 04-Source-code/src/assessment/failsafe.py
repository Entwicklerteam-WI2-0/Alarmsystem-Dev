"""Fail-safe-Logik fuer Stale-Daten, Plausibilitaet und DB-Ausfall (DTB-13).

Die Logik bleibt DB-agnostisch: sie arbeitet gegen das Repository-Interface
(get_latest, DTB-28) und vergleicht Zeitstempel ausschliesslich in UTC. MySQL-spezifische
Details (DATETIME(3), zeitzenlos) werden in der Persistenzschicht behandelt.

Bezug: NF-01; E-34; DTB-12; Schwellenwerte.md §3.
"""

import unicodedata
from datetime import datetime, timedelta

from src.config.loader import DatenqualitaetSchwellen
from src.model.enums import RiskLevel
from src.model.schemas import Assessment, Reading

# Maximale Laenge von Reason-Strings fuer Audit/Log-Ausgaben (NF-09).
MAX_REASON_LENGTH = 256

# Unicode-Kategorie, die in Audit-/Log-Reasons ersatzlos entfernt wird: Control
# Characters (Cc, inkl. U+007F DEL). Die Zeilentrenner U+2028/U+2029 (Zl/Zp) werden
# NICHT hier entfernt, sondern in _sanitize_reason vorab durch ein Leerzeichen ersetzt
# (Worttrennung erhalten) -> ein Filter-Eintrag waere wirkungslos und faelschlich
# "Entfernen statt Leerzeichen" (DTB-93 LOW).
_CONTROL_CATEGORIES = frozenset({"Cc"})


def is_stale(reading: Reading | None, now: datetime, timeout_s: float) -> bool:
    """Prueft, ob ein Reading als veraltet gilt.

    Args:
        reading: Das zu pruefende Reading. None gilt als veraltet (noch keine Daten).
        now: Referenzzeitpunkt (UTC), gegen den gemessen wird.
        timeout_s: Maximal erlaubtes Alter in Sekunden (kommt aus thresholds.json).

    Returns:
        True, wenn das Reading aelter als timeout_s ist oder fehlt.
    """
    # now wird unabhaengig vom reading uebergeben -> Validierung VOR dem None-Check,
    # damit ein naiver now-Wert auch dann frueh auffaellt, wenn das erste Reading in
    # einer Multi-Sensor-Schleife (DTB-38) None ist (DTB-93 LOW).
    if now.tzinfo is None:
        raise ValueError("now muss zeitzonenbewusst sein (UTC)")
    if reading is None:
        return True
    if reading.measured_at.tzinfo is None:
        raise ValueError("reading.measured_at muss zeitzonenbewusst sein (UTC)")
    if timeout_s <= 0:
        raise ValueError(f"timeout_s muss positiv sein, erhalten: {timeout_s}")
    age = now - reading.measured_at
    return age > timedelta(seconds=timeout_s)


def check_plausibility(
    current: Reading,
    previous: Reading | None,
    thresholds: DatenqualitaetSchwellen,
) -> str | None:
    """Prueft ein Reading auf Zeitstempelordnung und Temperatur-SPRUNG gegen ein vorheriges.

    Prueft ausschliesslich die beiden konsekutiv-paar-basierten Fehlerbilder laut
    Schwellenwerte.md §3; die Grenzwerte kommen aus thresholds.json (NF-05):
    - Zeitstempelordnung: previous muss zeitlich vor current liegen.
    - Sprung: Aenderung der Oberflaechentemperatur > thresholds.max_temp_jump_c_per_min.

    Flatline wird hier bewusst NICHT geprueft — sie braucht ein ZEITFENSTER (siehe
    check_flatline), das der Aufrufer (Poller) haelt. Diese Funktion und check_flatline
    sind komplementaer; keine ersetzt die andere.

    Args:
        current: Aktuelles Reading.
        previous: Vorheriges Reading desselben Sensors. Bei None kann keine
            Sprung-Pruefung stattfinden -> plausibel.
        thresholds: Parametrierbare Grenzwerte fuer Datenqualitaet.

    Returns:
        Menschenlesbarer Grund, wenn unplausibel; sonst None.
    """
    if previous is None:
        return None

    # Sicherstellen, dass keine Cross-Sensor-Vergleiche stattfinden.
    # Der Aufrufer ist dafuer verantwortlich, aber ein frueher Check verhindert
    # subtile Bugs in DTB-38. ValueError statt assert, damit der Guard auch unter
    # python -O (optimiert/Container) erhalten bleibt (NF-01).
    if current.sensor_id != previous.sensor_id:
        raise ValueError(
            f"check_plausibility erwartet denselben Sensor, "
            f"erhalten: {current.sensor_id!r} vs {previous.sensor_id!r}"
        )

    delta_t = current.measured_at - previous.measured_at
    if delta_t <= timedelta(seconds=0):
        # Negativer oder gleicher Zeitstempel ist ein Datenfehler -> unplausibel.
        return "invalid timestamp order"

    # Sub-Sekunden-Intervalle liefern keine sinnvolle Sprung-Rate;
    # Division durch fast-0 wuerde immer einen unplausibel hohen Wert ergeben.
    if delta_t < timedelta(seconds=1):
        return None

    delta_min = delta_t.total_seconds() / 60.0
    delta_temp_c = current.surface_temp_c - previous.surface_temp_c
    jump_rate = abs(delta_temp_c) / delta_min
    if jump_rate > thresholds.max_temp_jump_c_per_min:
        return f"temperature jump {jump_rate:.2f} C/min exceeds limit"

    # Flatline wird hier NICHT geprueft: sie braucht ein ZEITFENSTER (siehe check_flatline),
    # das der Aufrufer (Poller) haelt. check_plausibility deckt Zeitstempelordnung + Sprung ab.
    return None


def check_flatline(
    window_start: datetime | None,
    current_measured_at: datetime,
    temp_span_c: float,
    thresholds: DatenqualitaetSchwellen,
) -> str | None:
    """Flatline-Erkennung ueber ein ZEITFENSTER (FA-04, NF-01).

    `window_start` ist der Beginn (measured_at) des aktuellen Konstanz-Fensters — des
    aeltesten Readings, seit dem die Temperatur das Band nicht verlassen hat. `temp_span_c`
    ist die Spannweite (max-min) der Oberflaechentemperatur ueber dieses Fenster inkl. des
    aktuellen Readings. Flatline gilt, wenn das Fenster >= flatline_timeout_min lang ist UND
    die Spannweite <= flatline_epsilon_c bleibt (die Temperatur hat sich real nicht bewegt).

    Gegen ein Fenster statt gegen das unmittelbare Vorgaenger-Reading zu pruefen ist noetig,
    weil delta_min bei dichtem Polling (z. B. 30 s) sonst nie flatline_timeout_min erreicht
    (DTB-20 santa-loop). Die Spannweite ist ausserdem robuster gegen Rauschen als der Abstand
    zu einem einzelnen Punkt.

    WICHTIG (NF-05): flatline_epsilon_c ist die Rausch-/Bewegungstoleranz (Band). Sie muss zur
    realen Sensoraufloesung/zum Rauschen passen — ist sie zu klein, entkommt ein rauschender,
    eingefrorener Sensor der Erkennung. Der Wert ist mit dem Architekten/`Schwellenwerte.md`
    zu plausibilisieren, nicht im Code zu raten.

    Args:
        window_start: measured_at des Fensterbeginns. None -> kein Fenster -> plausibel.
        current_measured_at: measured_at des aktuellen Readings (Fensterende).
        temp_span_c: max-min der Oberflaechentemperatur ueber das Fenster inkl. current.
        thresholds: Parametrierbare Grenzwerte fuer Datenqualitaet (NF-05).

    Returns:
        "temperature flatline", wenn eingefroren; sonst None.

    Raises:
        ValueError: wenn current_measured_at oder ein gesetztes window_start nicht
            zeitzonenbewusst (UTC) ist — analog is_stale (DTB-20 LOW).
    """
    # TZ-Awareness analog zu is_stale erzwingen: naive datetimes liefern bei der
    # Subtraktion unten sonst einen stummen TypeError statt eines fruehen, klaren
    # Fehlers (DTB-20 LOW). Alle Zeitstempel laufen produktiv durch _parse_iso_utc,
    # der Guard schuetzt aber Aufrufer aus anderem Kontext.
    if current_measured_at.tzinfo is None:
        raise ValueError("current_measured_at muss zeitzonenbewusst sein (UTC)")
    if window_start is None:
        return None
    if window_start.tzinfo is None:
        raise ValueError("window_start muss zeitzonenbewusst sein (UTC)")
    delta_min = (current_measured_at - window_start).total_seconds() / 60.0
    if delta_min < thresholds.flatline_timeout_min:
        return None
    if temp_span_c <= thresholds.flatline_epsilon_c:
        return "temperature flatline"
    return None


def build_unknown_assessment(reason: str, ts: datetime) -> Assessment:
    """Baut einen fail-safe Assessment mit risk_level=unknown.

    Wird fuer getrennte Fail-safe-Faelle verwendet:
    - Stale-Daten (DTB-13): letztes Reading zu alt.
    - DB-Ausfall: Repository.get_latest() wirft RepositoryError.
    - Unplausible Daten: Sprung oder Flatline.

    Args:
        reason: Menschenlesbare Begruendung fuer Audit/Log. Sollte aus
            kontrollierter interner Logik stammen; wird auf 256 Zeichen
            gekuerzt und von Zeilenumbruechen bereinigt.
        ts: Zeitstempel der Bewertung (UTC).

    Returns:
        Assessment mit risk_level=RiskLevel.UNKNOWN.
    """
    safe_reason = _sanitize_reason(reason)
    return Assessment(
        ts=ts,
        risk_level=RiskLevel.UNKNOWN,
        explanation=f"Fail-safe: {safe_reason}",
    )


def _sanitize_reason(reason: str) -> str:
    """Bereinigt einen Reason-String fuer Audit/Log-Ausgaben.

    Verhindert, dass lange oder mehrzeilige Strings die Explanation
    aufblasen oder Formatierungsprobleme verursachen. Entfernt
    Zeilenumbrueche, Tabs und alle Control Characters (ASCII + Unicode).
    """
    # Zeilenumbrueche und Tabs durch Leerzeichen ersetzen (inkl. Unicode-
    # Zeilentrenner U+2028/U+2029, damit Worte nicht zusammenwachsen).
    cleaned = (
        reason.replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
        .replace("\u2028", " ")
        .replace("\u2029", " ")
    )
    # Verbleibende Control Characters entfernen (ASCII 0x00-0x1f, Unicode-Kategorie
    # Cc; U+007F DEL ist darueber mit abgedeckt). U+2028/U+2029 wurden oben bereits
    # zu Leerzeichen ersetzt und erreichen diesen Filter nicht mehr.
    cleaned = "".join(ch for ch in cleaned if unicodedata.category(ch) not in _CONTROL_CATEGORIES)
    cleaned = cleaned.strip()
    if len(cleaned) > MAX_REASON_LENGTH:
        cleaned = cleaned[: MAX_REASON_LENGTH - 3] + "..."
    return cleaned
