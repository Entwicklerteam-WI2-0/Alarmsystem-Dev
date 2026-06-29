"""G1-Poller: holt GET /current, validiert das Snapshot-JSON und speichert ein Reading.

Der Poller bleibt DB-agnostisch (ruft Repository.save; MySQL-Implementierung via DTB-28).
Er nutzt das Reading-Schema aus DTB-12 (src/model/schemas.py) und fuehrt keine
eigenstaendige Schema-Definition.

Bezug: Pull-Protokoll E-31; Datenmodell DTB-12; Persistenz DTB-28.
"""

import json
import logging
import math
import unicodedata
from datetime import UTC, datetime

import httpx

from src.assessment.failsafe import check_flatline, check_plausibility
from src.assessment.utils import calculate_dew_point
from src.config.loader import DatenqualitaetSchwellen, PlausibilitaetSchwellen
from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.repository import Repository, RepositoryError

logger = logging.getLogger(__name__)

# Pflichtfelder laut G1-Contract (Backend-Konzept §9.1).
REQUIRED_FIELDS = (
    "measured_at",
    "sensor_id",
    "surface_temp_c",
    "air_temp_c",
    "humidity_pct",
    "status",
)

# Unicode-Kategorien, die aus String-Feldern (z. B. sensor_id) entfernt werden, bevor sie
# geloggt/persistiert werden: Control (Cc, inkl. \n/\r/\t, U+007F), Format (Cf, inkl. U+202E
# RIGHT-TO-LEFT OVERRIDE und Zero-Width-Zeichen), die Zeilentrenner Zl/Zp (U+2028/U+2029)
# sowie alle Space-Separatoren Zs (U+0020 SPACE, U+00A0 NBSP, ...). sensor_id hat im
# Schema (src/model/schemas.py) KEIN Whitelist-Pattern; ein eingebettetes Leerzeichen
# ("anr rwy 01") wuerde sonst durchrutschen und als DB-Primaer-/Dictionary-Schluessel zu
# subtilen Lookup-Fehlern fuehren (DTB-20 Review L-2). Verhindert zusammen Log-/Audit-
# Injection, optische Manipulation und Schluessel-Drift. Konsistent mit und etwas strenger
# als _sanitize_reason in failsafe.py.
_UNSAFE_STRING_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp", "Zs"})

# Nach so vielen UNUNTERBROCHENEN Flatline-Verwerfungen desselben Pollers wird EINMALIG eine
# WARN-Zeile gesetzt (DTB-20 Review M-1). Zweck: ein echt eingefrorener Sensor und ein
# gesunder Sensor bei stabiler Kaelte erzeugen beide eine Dauer-Flatline-Sperre (E-42, K1);
# die WARN gibt dem Betriebs-Monitoring ein dediziertes Signal "dauerhaft kein Reading, aber
# kein Stale/Timeout" zum Nachsehen. Reine Log-Kadenz, KEINE Sicherheits-/Bewertungsschwelle
# -> bewusst Modul-Konstante (faellt nicht unter den config-Zwang NF-05, da sie kein
# Bewertungs-/Fail-safe-Verhalten aendert). 10 Polls = 5 min bei 30-s-Polling.
_FLATLINE_WARN_AFTER_N = 10


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
        # Letztes erfolgreich gespeichertes (plausibles) Reading desselben Sensors —
        # In-Memory-Referenz fuer die SPRUNG-Erkennung (DTB-20). Im Normalbetrieb aus dem
        # vorigen Poll. Nach einem Prozess-Neustart ist sie None und wird beim naechsten poll()
        # EINMALIG aus der DB nachgeladen (_load_baseline, PR#138 best-of-both mit DTB-20),
        # damit auch das erste Reading nach einem Neustart gegen den letzten persistierten Wert
        # auf Sprung geprueft wird. Der DB-Read ist best-effort -> bei Lesefehler
        # Cold-Start-Fallback (ein Zyklus ohne Sprung-Vergleich, fail-safe unkritisch).
        self._last_reading: Reading | None = None
        # Flatline-Fenster: Beginn (measured_at) der aktuellen Konstanz-Phase plus die ueber
        # das Fenster laufende Min/Max der Oberflaechentemperatur. Flatline prueft die
        # SPANNWEITE (max-min) ueber ein Zeitfenster (>= flatline_timeout_min), nicht den
        # Abstand zum unmittelbaren Vorgaenger — sonst waere die Erkennung bei dichtem Polling
        # wirkungslos und gegen Rauschen nicht robust (DTB-20 santa-loop, 2 Runden).
        self._flatline_window_start: datetime | None = None
        self._flatline_temp_min: float = 0.0
        self._flatline_temp_max: float = 0.0
        # Zaehler ununterbrochener Flatline-Verwerfungen (DTB-20 Review M-1). Wird bei jedem
        # erfolgreichen Save zurueckgesetzt; erreicht er _FLATLINE_WARN_AFTER_N, geht einmalig
        # eine WARN-Zeile raus (Eskalations-/Monitoring-Signal, kein Verhaltenswechsel).
        self._consecutive_flatline_rejections: int = 0

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
        # TODO (noch kein Jira-Ticket): wiederverwendeten httpx.Client einfuehren (Effizienz).
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

        # 5. Sensor-Defekt-Erkennung (DTB-20, FA-04/NF-01): Sprung + Flatline gegen die
        # bisherigen Referenzen DESSELBEN Sensors. Unplausibel -> fail-safe verwerfen (nicht
        # speichern); die Referenzen bleiben die letzten GUTEN Werte, damit ein einzelner
        # Ausreisser sie nicht vergiftet.
        # Neustart-Robustheit (PR#138 best-of-both): Ist die In-Memory-Referenz leer (frischer
        # Prozess), die Sprung-Baseline EINMALIG aus der DB nachladen, statt den ersten Poll
        # ungeprueft durchzulassen. Nur bei None -> im Normalbetrieb kein zusaetzlicher DB-Read.
        # Das Flatline-FENSTER wird bewusst NICHT aus der DB rekonstruiert (es baut sich nach
        # einem Neustart ueber flatline_timeout_min wieder auf; DTB-20-Restart-Verhalten bleibt).
        if self._last_reading is None:
            self._last_reading = self._load_baseline(reading.sensor_id)

        if self._last_reading is not None and self._last_reading.sensor_id != reading.sensor_id:
            # Sensorwechsel: Referenzen verwerfen statt Cross-Sensor zu vergleichen (haelt den
            # poll()-Contract 'Fehler -> None' ein; check_plausibility wuerfe sonst ValueError).
            self._last_reading = None
            self._reset_flatline_window()

        if self._last_reading is not None and reading.measured_at == self._last_reading.measured_at:
            # Identisches measured_at = G1 hat (noch) keinen neuen Wert geliefert (Poller pollt
            # ggf. schneller als G1 aktualisiert). Kein Defekt -> still ueberspringen, NICHT als
            # Fehler loggen (sonst Log-/Audit-Rauschen, vgl. santa-loop).
            logger.debug(
                "Kein neuer G1-Wert (gleiches measured_at=%s), uebersprungen",
                reading.measured_at.isoformat(),
            )
            return None

        # Sprung + Zeitstempelordnung gegen das unmittelbare Vorgaenger-Reading.
        # Hinweis (DTB-20 Review): Referenz UND Flatline-Fenster werden NUR nach einem
        # erfolgreichen Save aktualisiert. Verworfene Readings (Sprung/Flatline) lassen beide
        # unveraendert -> die Flatline-Uhr laeuft ab dem letzten GUTEN Reading weiter, auch
        # wenn dazwischen Werte als Sprung verworfen wurden. Kehrt der Sensor nach
        # >= flatline_timeout_min auf die alte Baseline zurueck, gilt das (fail-safe
        # konservativ) als Flatline.
        jump_reason = check_plausibility(reading, self._last_reading, self.data_quality_thresholds)
        if jump_reason is not None:
            # Sprung = reale (zu schnelle) Bewegung, das Gegenteil einer Flatline -> Zaehler
            # zuruecksetzen, damit "ununterbrochen flat" wirklich ununterbrochen bedeutet.
            self._consecutive_flatline_rejections = 0
            logger.error("Reading unplausibel, wird verworfen: %s", jump_reason)
            return None

        # Flatline gegen das Konstanz-FENSTER (Spannweite ueber >= flatline_timeout_min):
        # bei dichtem Polling waechst der Abstand zum Vorgaenger nie auf das Timeout, und die
        # Fenster-Spannweite ist gegen Rauschen robuster als der Abstand zu einem Punkt.
        span = self._flatline_span_including(reading)
        flatline_reason = check_flatline(
            self._flatline_window_start,
            reading.measured_at,
            span,
            self.data_quality_thresholds,
        )
        if flatline_reason is not None:
            self._consecutive_flatline_rejections += 1
            logger.error("Reading unplausibel, wird verworfen: %s", flatline_reason)
            # Einmalig beim Erreichen der Schwelle eskalieren (DTB-20 Review M-1): ein gesunder
            # Sensor bei stabiler Kaelte und ein echt eingefrorener Sensor sehen hier gleich aus;
            # die WARN markiert die Dauer-Sperre fuers Betriebs-Monitoring, ohne das fail-safe
            # Verhalten (immer verwerfen) zu aendern.
            if self._consecutive_flatline_rejections == _FLATLINE_WARN_AFTER_N:
                logger.warning(
                    "Sensor %s seit %d aufeinanderfolgenden Polls flatline-gesperrt "
                    "(stabile Kaelte ODER eingefrorener Sensor) - Betriebspruefung empfohlen; "
                    "Recovery via Temperaturbewegung > epsilon oder Poller-Neustart (E-42)",
                    reading.sensor_id,
                    self._consecutive_flatline_rejections,
                )
            return None

        # 6. Reading ueber das Repository-Interface speichern.
        try:
            reading_id = self.repository.save(reading)
        except RepositoryError as exc:
            logger.error("Speichern des Readings fehlgeschlagen: %s", exc)
            return None

        # Save erfolgreich -> Referenzen fuer den naechsten Poll aktualisieren.
        self._last_reading = reading
        self._update_flatline_window(reading)
        # Ein gespeichertes Reading beendet jede laufende Flatline-Sperre -> Zaehler zuruecksetzen.
        self._consecutive_flatline_rejections = 0

        logger.info(
            "Reading gespeichert: id=%s sensor=%s measured_at=%s",
            reading_id,
            reading.sensor_id,
            reading.measured_at.isoformat(),
        )
        # Reading MIT vergebener id zurueckgeben (copy-on-write, keine Mutation): der
        # Scheduler reicht diese Rueckgabe direkt an assess_reading weiter, das auf dem
        # Gutfall-Pfad reading.id != None verlangt (DTB-28-Invariante, service.py). Ohne
        # die id wuerde der Happy-Path des Schedulers mit ValueError brechen.
        return reading.model_copy(update={"id": reading_id})

    def _reset_flatline_window(self) -> None:
        """Setzt das Flatline-Konstanz-Fenster zurueck (z. B. bei Sensorwechsel).

        Recovery-Hinweis (E-42 / K1): Ein gesunder Sensor bei echtstabiler Kaelte (Span
        <= flatline_epsilon_c ueber >= flatline_timeout_min) wird dauerhaft als Flatline
        gesperrt — alle Folge-Readings werden verworfen, bis die Temperatur das Band real
        verlaesst. Der einzige MANUELLE Entsperr-Pfad ohne Temperaturbewegung ist ein
        Poller-Neustart (neues Poller-Objekt -> __init__ -> frisches Fenster). Ein
        automatischer Reset bei Flatline-Erkennung ist bewusst NICHT implementiert: er wuerde
        einen echt eingefrorenen Sensor periodisch wieder als gueltig akzeptieren
        (NF-01-Unteralarm). Ein tieferer Fix (Hysterese / Entsperr-Endpoint) ist eine offene
        Architektenentscheidung.
        """
        # 0.0 ist nur ein Dummy: _flatline_temp_min/max sind ausschliesslich gueltig, wenn
        # _flatline_window_start gesetzt ist. Beide Konsumenten (_flatline_span_including,
        # _update_flatline_window) guarden auf window_start is None und lesen die 0.0 nie.
        self._flatline_window_start = None
        self._flatline_temp_min = 0.0
        self._flatline_temp_max = 0.0

    def _flatline_span_including(self, reading: Reading) -> float:
        """Spannweite (max-min) der Oberflaechentemperatur ueber das laufende Fenster INKL. des
        aktuellen Readings. 0.0, wenn (noch) kein Fenster offen ist (-> check_flatline plausibel).
        """
        if self._flatline_window_start is None:
            return 0.0
        temp = reading.surface_temp_c
        return max(self._flatline_temp_max, temp) - min(self._flatline_temp_min, temp)

    def _update_flatline_window(self, reading: Reading) -> None:
        """Aktualisiert das Konstanz-Fenster nach einem gespeicherten Reading.

        Bleibt die Spannweite (max-min) inkl. des neuen Readings <= flatline_epsilon_c, waechst
        das Fenster (gleicher Startzeitpunkt) -> der Abstand zum Fensterbeginn waechst, bis
        flatline_timeout_min erreicht ist und check_flatline anschlaegt. Verlaesst die Temperatur
        das Band (Spannweite > epsilon = reale Bewegung), beginnt das Fenster neu (DTB-20).
        """
        temp = reading.surface_temp_c
        if self._flatline_window_start is None:
            self._flatline_window_start = reading.measured_at
            self._flatline_temp_min = temp
            self._flatline_temp_max = temp
            return
        new_min = min(self._flatline_temp_min, temp)
        new_max = max(self._flatline_temp_max, temp)
        if new_max - new_min > self.data_quality_thresholds.flatline_epsilon_c:
            # Temperatur hat das Band verlassen -> reale Bewegung -> Fenster neu starten.
            self._flatline_window_start = reading.measured_at
            self._flatline_temp_min = temp
            self._flatline_temp_max = temp
        else:
            self._flatline_temp_min = new_min
            self._flatline_temp_max = new_max

    def _load_baseline(self, sensor_id: str) -> Reading | None:
        """Laedt das letzte persistierte Reading als Sprung-Baseline (Neustart-Robustheit, PR#138).

        Wird nur aufgerufen, wenn die In-Memory-Referenz leer ist (frischer Prozess). Best-effort:
        Bei einem DB-Lesefehler None zurueckgeben (Cold-Start-Fallback) statt ein gueltiges
        Reading zu verwerfen — der fehlende Sprung-Vergleich fuer EINEN Zyklus ist fail-safe
        unkritisch (die uebrigen Eingangspruefungen aus _build_reading greifen weiterhin).
        """
        try:
            previous = self.repository.get_latest(sensor_id, limit=1)
        except RepositoryError as exc:
            logger.warning("Sprung-Baseline aus DB nicht lesbar, Cold-Start-Fallback: %s", exc)
            return None
        return previous[0] if previous else None

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
            status = _as_status(data["status"])
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

        # Optionale G1-Kontextfelder (Contract v1.1): surface_moisture_pct (kalibrierte
        # Oberflaechenfeuchte %) und wind_speed_ms (Windgeschwindigkeit m/s). Reine Speicher-/
        # Anzeigewerte -> fliessen NICHT in die Bewertung, daher bewusst KEINE config-
        # Plausibilitaetsschwelle (blaeht NF-05 nicht auf). Ein defekter Wert wird auf None
        # gesetzt und blockiert die Pflicht-Trias nie (Fail-safe); _optional_float faengt
        # bool/inf/Nicht-Zahl ab (NF-01). G2 nimmt bewusst nur die kalibrierten/SI-Werte,
        # nicht die G1-Rohwerte (surface_moisture_raw, wind_speed_kmh, wind_raw).
        optional_context: dict[str, float | None] = {
            "surface_moisture_pct": None,
            "wind_speed_ms": None,
        }
        for context_field in optional_context:
            try:
                optional_context[context_field] = _optional_float(
                    data.get(context_field), context_field
                )
            except ValueError as exc:
                logger.error("G1-Feld ungueltig: %s", exc)

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
            surface_moisture_pct=optional_context["surface_moisture_pct"],
            wind_speed_ms=optional_context["wind_speed_ms"],
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
        logger.warning("Taupunkt ist nicht endlich: %s", dew_point_c)
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
    # ISO-8601-String -> UTC. Akzeptiert JEDE zeitzonenbewusste Notation (Z, +00:00,
    # +02:00, -05:00, ...) und normalisiert eindeutig auf UTC. NAIVE (zeitzonenlose)
    # Strings werden bewusst abgelehnt (Fail-safe, NF-01): "lokal oder UTC?" darf nicht
    # geraten werden -- ein stiller 1-2 h-Versatz (z. B. Sommerzeit) wuerde Stale-/
    # Zukunfts-Pruefung und Bewertung verfaelschen. Frueher nur Z/+00:00; gelockert fuer
    # G1-Quellen mit lokalem Offset (Plan measured_at-UTC-Fix Option B). Contract §2a D
    # (alle Zeitstempel UTC) bleibt gewahrt -- die astimezone-Konvertierung stellt das sicher.
    if not isinstance(value, str):
        raise ValueError(f"measured_at muss ein String sein, erhalten: {type(value)}")
    # 'Z' ist gueltiges ISO-8601, datetime.fromisoformat akzeptiert es erst ab Python 3.11
    # zuverlaessig -> auf +00:00 normalisieren (nur ein abschliessendes Z, nicht alle Vorkommen).
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            f"measured_at ist kein gueltiger ISO-8601-Zeitstempel: {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError("measured_at muss Zeitzoneninformation enthalten (Z oder Offset)")
    return parsed.astimezone(UTC)


def _as_string(value: object, field: str) -> str:
    # Pflicht-String-Felder muessen nicht-leer sein.
    if not isinstance(value, str):
        raise ValueError(f"{field} muss ein String sein, erhalten: {type(value)}")
    stripped = value.strip()
    # Eingebettete unsichere Zeichen entfernen (Control/Format/Zeilentrenner/Space-Separatoren,
    # siehe _UNSAFE_STRING_CATEGORIES): ein manipuliertes G1-Feld wie "anr-rwy-01\n[AUDIT] ..."
    # mit U+202E (RTL-Override, optische Umkehr) oder mit eingebettetem Leerzeichen
    # ("anr rwy 01" -> Schluessel-Drift) koennte sonst eine gefaelschte/irrefuehrende Log-/
    # Audit-Zeile oder einen falschen DB-/Dictionary-Schluessel erzeugen (DTB-20 Review).
    # Aeusserer Whitespace ist oben bereits entfernt; dieser Filter trifft nur noch
    # eingebettete Zeichen.
    stripped = "".join(
        ch for ch in stripped if unicodedata.category(ch) not in _UNSAFE_STRING_CATEGORIES
    )
    if not stripped:
        raise ValueError(f"{field} darf nicht leer sein")
    return stripped


def _as_float(value: object, field: str) -> float:
    # Pflicht-Zahlenfelder muessen JSON-Zahlen sein (int oder float).
    # bool ist in Python ein int-Subtyp und wuerde stumm zu 0.0/1.0 werden — das ist
    # fuer defekte G1-Payloads (z. B. "surface_temp_c": true) gefaehrlich (NF-01).
    # Strings wie "23.5" werden ebenfalls abgelehnt (Contract verlangt JSON-Zahl).
    if isinstance(value, bool):
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: bool ({value!r})")
    if not isinstance(value, int | float):
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: {type(value)}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} muss endlich sein, erhalten: {value!r}")
    return result


def _optional_float(value: object, field: str) -> float | None:
    # Optionale Zahlenfelder: None ist erlaubt, sonst gelten dieselben Regeln wie
    # fuer Pflicht-Zahlenfelder (keine Code-Duplikation, NF-01).
    if value is None:
        return None
    return _as_float(value, field)


def _as_status(value: object) -> SensorStatus:
    # Pflichtfeld G1-Status (Backend-Konzept §9.1): muss im Enum liegen.
    # Defekte Werte werfen ValueError (wie die uebrigen Feld-Parser) -> zentrale
    # Fail-safe-Behandlung in _build_reading.
    if not isinstance(value, str):
        raise ValueError(f"status muss ein String sein, erhalten: {type(value)}")
    try:
        return SensorStatus(value)
    except ValueError as exc:
        raise ValueError(f"Ungueltiger status-Wert: {value!r}") from exc
