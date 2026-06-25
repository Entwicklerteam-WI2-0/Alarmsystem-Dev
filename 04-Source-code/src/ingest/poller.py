"""G1-Poller: holt GET /current, validiert das Snapshot-JSON und speichert ein Reading.

Der Poller bleibt DB-agnostisch (ruft Repository.save; MySQL-Implementierung via DTB-28).
Er nutzt das Reading-Schema aus DTB-12 (src/model/schemas.py) und fuehrt keine
eigenstaendige Schema-Definition.

Bezug: Pull-Protokoll E-31; Datenmodell DTB-12; Persistenz DTB-28.
"""

import json
import logging
import math
from datetime import UTC, datetime, timedelta

import httpx

from src.assessment.utils import calculate_dew_point
from src.config.loader import DatenqualitaetSchwellen, PlausibilitaetSchwellen
from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.repository import Repository, RepositoryError

logger = logging.getLogger(__name__)

# Pflichtfelder laut G1-Contract (Backend-Konzept §9.1).
REQUIRED_FIELDS = ("measured_at", "sensor_id", "surface_temp_c", "air_temp_c", "humidity_pct")


def _now() -> datetime:
    # In eine Helper-Funktion gekapselt, damit Tests die Uhr deterministisch patchen koennen
    # (die Stale-Erkennung haengt von der aktuellen Zeit ab).
    return datetime.now(UTC)


class Poller:
    """HTTP-Client gegen G1 GET /current mit Eingangsvalidierung."""

    def __init__(
        self,
        base_url: str,
        repository: Repository,
        data_quality_thresholds: DatenqualitaetSchwellen,
        plausibility_thresholds: PlausibilitaetSchwellen,
        timeout: float = 10.0,
    ) -> None:
        # Base-URL ohne abschliessenden Slash, damit /current sauber angehaengt wird.
        self.base_url = base_url.rstrip("/")
        # Speicherschicht wird injiziert -> Poller bleibt DB-agnostisch.
        self.repository = repository
        # Parametrierbare Grenzwerte fuer Datenqualitaet (Stale-Timeout, Clock-Skew, ...)
        # und fuer die physikalische Plausibilitaet der Eingangswerte.
        # Muessen vom Aufrufer geladen werden (config/thresholds.json), damit NF-05 eingehalten
        # wird und keine Schwellen im Poller hardgecoded sind.
        self.data_quality_thresholds = data_quality_thresholds
        self.plausibility_thresholds = plausibility_thresholds
        # Timeout fuer den HTTP-Request (Netzwerk/Sensor-Ausfall).
        self.timeout = timeout

    def poll(self) -> Reading | None:
        """Holt Snapshot von G1, validiert ihn und speichert ein Reading.

        Fragt zuerst GET /health ab; bei 503 oder jedem HTTP-Fehler wird das
        Snapshot verworfen (Fail-safe, NF-01). Erst bei 200 OK wird /current
        gepollt.

        Bei jeder Art von Fehler (HTTP, Parsing, fehlende Pflichtfelder,
        Out-of-Range) wird geloggt und None zurueckgegeben -> kein Speichern,
        kein GRUEN (Fail-safe).
        """
        # 1. Verfuegbarkeits-Check: G1 muss vor /current gesund sein.
        if not self._is_g1_healthy():
            return None

        url = f"{self.base_url}/current"

        # 2. HTTP-Request an G1 senden.
        # TODO: Wiederverwendeten httpx.Client einfuehren (Effizienz, DTB-??).
        # Aktuell bewusst httpx.get, weil ein Client-Wechsel alle Poller-Tests
        # umstellen wuerde; sollte in einem dedizierten Refactoring erfolgen.
        try:
            response = httpx.get(url, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("G1-Poll fehlgeschlagen: %s", exc)
            return None

        # 3. Antwort als JSON parsen.
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            logger.error("G1-Antwort nicht als JSON parsierbar: %s", exc)
            return None

        # 4. Validieren und in das Reading-Schema ueberfuehren.
        reading = self._build_reading(data)
        if reading is None:
            return None

        # 5. Reading ueber das Repository-Interface speichern.
        try:
            reading_id = self.repository.save(reading)
        except RepositoryError as exc:
            logger.error("Speichern des Readings fehlgeschlagen: %s", exc)
            return None

        logger.info(
            "Reading gespeichert: id=%s sensor=%s measured_at=%s",
            reading_id,
            reading.sensor_id,
            reading.measured_at.isoformat(),
        )
        return reading

    def _is_g1_healthy(self) -> bool:
        """Ruft GET /health ab; gibt True bei 200 OK, sonst False."""
        url = f"{self.base_url}/health"
        try:
            response = httpx.get(url, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("G1-Health-Check fehlgeschlagen: %s", exc)
            return False
        return True

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

        # Pflichtfelder + status (optional, aber defekter Wert verwirft Reading).
        # Alle Feld-Parser werfen bei defektem Wert ValueError, die hier zentral
        # fail-safe zu None fuehrt (NF-01).
        try:
            measured_at = _parse_iso_utc(data["measured_at"])
            sensor_id = _as_string(data["sensor_id"], "sensor_id")
            surface_temp_c = _as_float(data["surface_temp_c"], "surface_temp_c")
            air_temp_c = _as_float(data["air_temp_c"], "air_temp_c")
            humidity_pct = _as_float(data["humidity_pct"], "humidity_pct")
            status = _optional_status(data.get("status"))
        except ValueError as exc:
            logger.error("G1-Feld ungueltig: %s", exc)
            return None

        # Optionales pressure_hpa: defekter Wert wird geloggt und auf None gesetzt,
        # das Reading wird trotzdem gespeichert (Kontextfeld darf die Pflicht-Trias
        # aus surface_temp_c, air_temp_c und humidity_pct nicht blockieren).
        pressure_hpa: float | None = None
        try:
            pressure_hpa = _optional_float(data.get("pressure_hpa"), "pressure_hpa")
        except ValueError as exc:
            logger.error("G1-Feld ungueltig: %s", exc)
            pressure_hpa = None

        if pressure_hpa is not None and not (
            self.plausibility_thresholds.min_pressure_hpa
            <= pressure_hpa
            <= self.plausibility_thresholds.max_pressure_hpa
        ):
            logger.error("pressure_hpa ausserhalb des gueltigen Bereichs: %s", pressure_hpa)
            pressure_hpa = None

        # Sensor meldet selbst einen Defekt -> Reading ablehnen (Fail-safe, NF-01).
        if status is SensorStatus.FAULT:
            logger.error("G1-Sensor meldet status=fault, Reading wird verworfen")
            return None

        # Stale-Erkennung (FA-04, NF-01): zu alte Snapshots fail-safe verwerfen, damit kein
        # veralteter Wert als aktuell gespeichert wird (downstream nie still GRUEN).
        # received_at wird einmal bestimmt und sowohl fuer die Pruefung als auch fuer das
        # Reading genutzt.
        received_at = _now()
        age_s = (received_at - measured_at).total_seconds()
        max_clock_skew_s = self.data_quality_thresholds.max_clock_skew_s
        if age_s < -max_clock_skew_s:
            logger.error(
                "G1-Snapshot-Zeit liegt in der Zukunft (skew=%.0f s > %.1f s) - verworfen",
                -age_s,
                max_clock_skew_s,
            )
            return None
        stale_timeout_s = self.data_quality_thresholds.stale_timeout_s
        if age_s > stale_timeout_s:
            logger.error(
                "G1-Snapshot veraltet (%.0f s > %.1f s), Reading wird verworfen",
                age_s,
                stale_timeout_s,
            )
            return None

        # Plausibilitaet: Temperatur-/Feuchte-Werte muessen in den parametrierbaren
        # Grenzen liegen (NF-05: aus config/thresholds.json, nicht hardgecoded).
        if not (
            self.plausibility_thresholds.min_temp_c
            <= surface_temp_c
            <= self.plausibility_thresholds.max_temp_c
        ):
            logger.error("surface_temp_c ausserhalb des gueltigen Bereichs: %s", surface_temp_c)
            return None
        if not (
            self.plausibility_thresholds.min_temp_c
            <= air_temp_c
            <= self.plausibility_thresholds.max_temp_c
        ):
            logger.error("air_temp_c ausserhalb des gueltigen Bereichs: %s", air_temp_c)
            return None
        if not (
            self.plausibility_thresholds.min_humidity_pct
            <= humidity_pct
            <= self.plausibility_thresholds.max_humidity_pct
        ):
            logger.error("humidity_pct ausserhalb des gueltigen Bereichs: %s", humidity_pct)
            return None

        # Taupunkt fail-safe berechnen (Magnus, DTB-32). None = unbestimmbar/unplausibel
        # -> downstream konservativ (nie still GRUEN, NF-01). air_temp_c/humidity_pct sind
        # hier bereits als endlich und im Plausibilitaetsbereich validiert.
        dew_point_c = _compute_dew_point(
            air_temp_c,
            humidity_pct,
            self.data_quality_thresholds.min_plausible_dew_point_c,
        )

        # Validierte Werte in das DTB-12 Reading-Schema ueberfuehren.
        return Reading(
            sensor_id=sensor_id,
            measured_at=measured_at,
            surface_temp_c=surface_temp_c,
            air_temp_c=air_temp_c,
            humidity_pct=humidity_pct,
            dew_point_c=dew_point_c,
            pressure_hpa=pressure_hpa,
            status=status,
            received_at=received_at,
            source=Source.REAL,
        )


def _compute_dew_point(
    air_temp_c: float, humidity_pct: float, min_plausible_dew_point_c: float
) -> float | None:
    """Berechnet den Taupunkt (Magnus, DTB-32) fail-safe als float oder None.

    None statt eines Ersatzwertes, wenn der Taupunkt nicht bestimmbar ist
    (RH=0 -> calculate_dew_point wirft ValueError) oder das Ergebnis unplausibel
    ist (< min_plausible_dew_point_c, z. B. bei RH knapp ueber 0). None bedeutet
    downstream "unbestimmbar": die Bewertung (DTB-38) stuft konservativ ein und
    gibt nie still GRUEN aus (NF-01).

    Voraussetzung: air_temp_c und humidity_pct sind bereits als endlich und im
    Plausibilitaetsbereich validiert.
    """
    try:
        dew_point_c = calculate_dew_point(air_temp_c, humidity_pct)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        # Defense-in-depth: auch unerwartete Berechnungsfehler fangen und konservativ
        # als "unbestimmbar" behandeln, damit der Poller-Cycle nicht abbricht (NF-01).
        logger.warning("Taupunkt nicht berechenbar (dew_point_c=None): %s", exc)
        return None

    if not math.isfinite(dew_point_c):
        logger.warning("Taupunkt ist nicht endlich (dew_point_c=%s), dew_point_c=None", dew_point_c)
        return None

    if dew_point_c < min_plausible_dew_point_c:
        logger.warning(
            "Taupunkt unplausibel (%s < %s), dew_point_c=None",
            dew_point_c,
            min_plausible_dew_point_c,
        )
        return None

    return dew_point_c


def _parse_iso_utc(value: object) -> datetime:
    # ISO-8601-String mit UTC-Zeitzone erzwingen (z. B. 2026-06-23T10:00:00Z).
    if not isinstance(value, str):
        raise ValueError(f"measured_at muss ein String sein, erhalten: {type(value)}")
    # Python <3.11 akzeptiert 'Z' nicht direkt; ab 3.11 geht es.
    # Bewusst nur ein abschliessendes Z ersetzen, nicht alle Vorkommen im String.
    if value.endswith("Z"):
        normalized = value[:-1] + "+00:00"
    elif value.endswith("+00:00"):
        normalized = value
    else:
        raise ValueError("measured_at muss UTC sein (Z oder +00:00)")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("measured_at muss Zeitzoneninformation enthalten (UTC)")
    # Sicherstellen, dass der Offset wirklich 0 ist (z. B. +00:00).
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("measured_at muss UTC sein")
    return parsed.astimezone(UTC)


def _as_string(value: object, field: str) -> str:
    # Pflicht-String-Felder muessen nicht-leer sein.
    if not isinstance(value, str):
        raise ValueError(f"{field} muss ein String sein, erhalten: {type(value)}")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field} darf nicht leer sein")
    # Whitespace am Rand verhindert spaetere sensor_id-Lookups (z. B. in DB).
    return stripped


def _as_float(value: object, field: str) -> float:
    # Pflicht-Zahlenfelder muessen in float konvertierbar sein.
    # bool ist in Python ein int-Subtyp und wuerde stumm zu 0.0/1.0 werden — das ist
    # fuer defekte G1-Payloads (z. B. "surface_temp_c": true) gefaehrlich (NF-01).
    if isinstance(value, bool):
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: bool ({value!r})")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: {value!r}") from exc


def _optional_float(value: object, field: str) -> float | None:
    # Optionale Zahlenfelder: None ist erlaubt, sonst float-Konvertierung.
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: bool ({value!r})")
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
