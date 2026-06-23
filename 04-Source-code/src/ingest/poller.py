"""G1-Poller: holt GET /current, validiert das Snapshot-JSON und speichert ein Reading.

Der Poller bleibt DB-agnostisch (ruft Repository.save; MySQL-Implementierung via DTB-28).
Er nutzt das Reading-Schema aus DTB-12 (src/model/schemas.py) und fuehrt keine
eigenstaendige Schema-Definition.

Bezug: Pull-Protokoll E-31; Datenmodell DTB-12; Persistenz DTB-28.
"""

import logging
from datetime import UTC, datetime

import httpx

from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.repository import Repository

logger = logging.getLogger(__name__)

# Physikalische Plausibilitaetsgrenzen fuer die Eingangsvalidierung.
# (Bewertungsschwellen kommen aus config/ und werden hier NICHT hardgecoded.)
MIN_TEMP_C = -50.0
MAX_TEMP_C = 50.0
MIN_HUMIDITY_PCT = 0.0
MAX_HUMIDITY_PCT = 100.0
MIN_PRESSURE_HPA = 800.0
MAX_PRESSURE_HPA = 1100.0

# Pflichtfelder laut G1-Contract (Backend-Konzept §9.1).
REQUIRED_FIELDS = ("measured_at", "sensor_id", "surface_temp_c", "air_temp_c", "humidity_pct")


class Poller:
    """HTTP-Client gegen G1 GET /current mit Eingangsvalidierung."""

    def __init__(self, base_url: str, repository: Repository, timeout: float = 10.0) -> None:
        # Base-URL ohne abschliessenden Slash, damit /current sauber angehaengt wird.
        self.base_url = base_url.rstrip("/")
        # Speicherschicht wird injiziert -> Poller bleibt DB-agnostisch.
        self.repository = repository
        # Timeout fuer den HTTP-Request (Netzwerk/Sensor-Ausfall).
        self.timeout = timeout

    def poll(self) -> Reading | None:
        """Holt Snapshot von G1, validiert ihn und speichert ein Reading.

        Bei jeder Art von Fehler (HTTP, Parsing, fehlende Pflichtfelder,
        Out-of-Range) wird geloggt und None zurueckgegeben -> kein Speichern,
        kein GRUEN (Fail-safe).
        """
        url = f"{self.base_url}/current"

        # 1. HTTP-Request an G1 senden.
        try:
            response = httpx.get(url, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("G1-Poll fehlgeschlagen: %s", exc)
            return None

        # 2. Antwort als JSON parsen.
        try:
            data = response.json()
        except Exception as exc:
            logger.error("G1-Antwort nicht als JSON parsierbar: %s", exc)
            return None

        # 3. Validieren und in das Reading-Schema ueberfuehren.
        reading = self._build_reading(data)
        if reading is None:
            return None

        # 4. Reading ueber das Repository-Interface speichern.
        try:
            reading_id = self.repository.save(reading)
        except Exception as exc:
            logger.error("Speichern des Readings fehlgeschlagen: %s", exc)
            return None

        logger.info(
            "Reading gespeichert: id=%s sensor=%s measured_at=%s",
            reading_id,
            reading.sensor_id,
            reading.measured_at.isoformat(),
        )
        return reading

    def _build_reading(self, data: object) -> Reading | None:
        # Pruefung: G1 muss ein JSON-Objekt liefern, keine Liste/Zahl.
        if not isinstance(data, dict):
            logger.error("G1-Antwort ist kein JSON-Objekt: %s", type(data))
            return None

        # Pruefung: alle Pflichtfelder des G1-Contracts vorhanden.
        for field in REQUIRED_FIELDS:
            if field not in data:
                logger.error("Pflichtfeld in G1-Antwort fehlt: %s", field)
                return None

        # Design (NF-01, bewusst defensiv): Ein FEHLENDES optionales Feld ist ok
        # (pressure_hpa -> None, status -> Default OK). Ein VORHANDENES, aber DEFEKTES
        # optionales Feld (nicht-numerisches pressure_hpa, ungueltiger status) verwirft
        # das GESAMTE Reading -- lieber nichts speichern als halb-validierte Daten.
        # Einheitliches Muster: alle Feld-Parser (Pflicht UND optional) werfen bei
        # defektem Wert ValueError, die hier zentral fail-safe zu None fuehrt.
        try:
            measured_at = _parse_iso_utc(data["measured_at"])
            sensor_id = _as_string(data["sensor_id"], "sensor_id")
            surface_temp_c = _as_float(data["surface_temp_c"], "surface_temp_c")
            air_temp_c = _as_float(data["air_temp_c"], "air_temp_c")
            humidity_pct = _as_float(data["humidity_pct"], "humidity_pct")
            pressure_hpa = _optional_float(data.get("pressure_hpa"), "pressure_hpa")
            status = _optional_status(data.get("status"))
        except ValueError as exc:
            logger.error("G1-Feld ungueltig: %s", exc)
            return None

        # Plausibilitaet: Temperatur-/Feuchte-Werte muessen in physikalischen Grenzen liegen.
        if not (MIN_TEMP_C <= surface_temp_c <= MAX_TEMP_C):
            logger.error("surface_temp_c ausserhalb des gueltigen Bereichs: %s", surface_temp_c)
            return None
        if not (MIN_TEMP_C <= air_temp_c <= MAX_TEMP_C):
            logger.error("air_temp_c ausserhalb des gueltigen Bereichs: %s", air_temp_c)
            return None
        if not (MIN_HUMIDITY_PCT <= humidity_pct <= MAX_HUMIDITY_PCT):
            logger.error("humidity_pct ausserhalb des gueltigen Bereichs: %s", humidity_pct)
            return None

        # Plausibilitaet des optionalen pressure_hpa (Parsing erfolgte oben im Fail-safe-try).
        if pressure_hpa is not None and not (MIN_PRESSURE_HPA <= pressure_hpa <= MAX_PRESSURE_HPA):
            logger.error("pressure_hpa ausserhalb des gueltigen Bereichs: %s", pressure_hpa)
            return None

        # Validierte Werte in das DTB-12 Reading-Schema ueberfuehren.
        return Reading(
            sensor_id=sensor_id,
            measured_at=measured_at,
            surface_temp_c=surface_temp_c,
            air_temp_c=air_temp_c,
            humidity_pct=humidity_pct,
            pressure_hpa=pressure_hpa,
            status=status,
            received_at=datetime.now(UTC),
            source=Source.REAL,
        )


def _parse_iso_utc(value: object) -> datetime:
    # ISO-8601-String mit Zeitzone erzwingen (z. B. 2026-06-23T10:00:00Z).
    if not isinstance(value, str):
        raise ValueError(f"measured_at muss ein String sein, erhalten: {type(value)}")
    # Python <3.11 akzeptiert 'Z' nicht direkt; ab 3.11 geht es.
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("measured_at muss Zeitzoneninformation enthalten (UTC)")
    return parsed.astimezone(UTC)


def _as_string(value: object, field: str) -> str:
    # Pflicht-String-Felder muessen nicht-leer sein.
    if not isinstance(value, str):
        raise ValueError(f"{field} muss ein String sein, erhalten: {type(value)}")
    if not value.strip():
        raise ValueError(f"{field} darf nicht leer sein")
    return value


def _as_float(value: object, field: str) -> float:
    # Pflicht-Zahlenfelder muessen in float konvertierbar sein.
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: {value!r}") from exc


def _optional_float(value: object, field: str) -> float | None:
    # Optionale Zahlenfelder: None ist erlaubt, sonst float-Konvertierung.
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: {value!r}") from exc


def _optional_status(value: object) -> SensorStatus:
    # Optionaler G1-Status: fehlend -> Default OK; sonst muss der Wert im Enum liegen.
    # Defekte Werte werfen ValueError (wie die uebrigen Feld-Parser) -> zentrale
    # Fail-safe-Behandlung in _build_reading (kein stilles None mehr).
    if value is None:
        return SensorStatus.OK
    if not isinstance(value, str):
        raise ValueError(f"status muss ein String sein, erhalten: {type(value)}")
    try:
        return SensorStatus(value)
    except ValueError as exc:
        raise ValueError(f"Ungueltiger status-Wert: {value!r}") from exc
