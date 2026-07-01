"""Assessment-Orchestrierung (DTB-64): verbindet Reading -> Bewertung -> Persistenz -> Audit.

Hier — NICHT in der reinen `assess_ice_risk` — lebt das **NF-01-Enforcement zur
Laufzeit**: `assess_ice_risk` ist eine reine Funktion ohne Daten-Kontext und kennt
weder Stale noch Sensor-Status. Dieser Service kapselt sie und erzwingt den
Fail-safe an zwei Stellen:

1. **Assess-Zeit** (`AssessmentService.assess_reading`): pro Poll-Zyklus — bei
   fehlenden / veralteten (stale) / defekten (fault) Daten wird `unknown`
   erzeugt (nie GRUEN), sonst regulaer bewertet; danach persistiert + auditiert.
2. **Serve-Zeit** (`build_assessment_current`): beim Ausliefern via
   GET /v1/assessment/current wird die Aktualitaet ERNEUT geprueft (das zuletzt
   gespeicherte Reading kann inzwischen veraltet sein) und der Wire-Response
   nach Contract gebaut — `green` nur bei `is_stale=false` UND `sensor_status=ok`.

Bezug: NF-01, Schwellenwerte.md §2/§3, Contract v1 (AssessmentCurrent, E-36),
Kapselt: assess_ice_risk (DTB-38), is_stale/build_unknown_assessment (DTB-13).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from src.assessment.core import (
    DRIVING_FACTOR_SENSOR_DATA,
    DRIVING_FACTOR_SENSOR_FAULT,
    DRIVING_FACTOR_STALE,
    MAX_EXPLANATION_LEN,
    assess_ice_risk,
    derive_explanation,
)
from src.assessment.failsafe import build_unknown_assessment, is_stale
from src.config.loader import Thresholds

# TYPE_CHECKING: bricht den Circular Import. riskhysterese.py importiert
# assess_ice_risk aus src.assessment.core und triggert damit assessment/__init__.py,
# das service.py laedt. Wuerde service.py RiskHysterese zur Ladezeit importieren,
# entstuende ein Ring. Dank `from __future__ import annotations` sind alle
# Annotationen Strings und werden nicht zur Laufzeit ausgewertet -> der Typ ist nur
# fuer statische Pruefung noetig (TYPE_CHECKING-Zweig).
if TYPE_CHECKING:
    from src.alarm.riskhysterese import RiskHysterese
from src.model.enums import AuditEventType, RiskLevel, SensorStatus
from src.model.schemas import (
    Assessment,
    AssessmentCurrent,
    AuditLogEntry,
    Reading,
)
from src.storage.assessment_repository import AssessmentRepository
from src.storage.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


class AssessmentService:
    """Fuehrt EINEN Bewertungszyklus aus und persistiert das Ergebnis (DTB-64).

    Args:
        thresholds: Geladene, validierte Schwellen (DTB-15) — Quelle u. a. fuer
            den Stale-Timeout und alle Vereisungs-Schwellen (keine Hardcodes).
        assessment_repo: Persistenz fuer Bewertungen (F10).
        audit_repo: Append-only Audit-Log (DTB-29, NF-09).
    """

    def __init__(
        self,
        thresholds: Thresholds,
        risk_hysterese: RiskHysterese,
        assessment_repo: AssessmentRepository,
        audit_repo: AuditRepository,
        threshold_set_id: int | None = None,
    ) -> None:
        self._thresholds = thresholds
        # DTB-27 Anzeige-Hysterese (RiskHysterese): zustandsbehaftet, pro Sensor einmal
        # (Single-Sensor). Wird in JEDEM Poll-Zyklus exakt EINMAL getickt — im Gutfall
        # via bewerten(), in den Fail-safe-Pfaden via uebernimm_unknown(). So durchlaeuft
        # die Zustandsmaschine immer den UNKNOWN-Durchgang bei Stale/Fault und recoveryt
        # beim naechsten Gutfall sofort (Spezifikation: Recovery aus Unsicherheit),
        # statt auf der letzten Gutfall-Stufe kleben zu bleiben (State-Desync).
        self._risk_hysterese = risk_hysterese
        self._assessment_repo = assessment_repo
        self._audit_repo = audit_repo
        # DTB-65: id des aktiven threshold_set (DB) -> wird auf jedes Assessment gestempelt
        # (NF-05-Traceability: welcher Schwellensatz galt). None, wenn die Schwellen aus der
        # JSON-Seed-Config kommen (kein persistierter Satz). Pro laufende Instanz fix
        # (Reload-on-Restart-Semantik, DTB-63).
        self._threshold_set_id = threshold_set_id

    def assess_reading(
        self,
        reading: Reading | None,
        now: datetime,
        forecast_surface_temp_c: float | None = None,
    ) -> Assessment:
        """Bewertet ein (frisch gepolltes) Reading, persistiert + auditiert das Ergebnis.

        NF-01-Enforcement (Reihenfolge bewusst, Fail-safe vor Bewertung):
        keine Daten / fault / stale -> `unknown` (nie GRUEN); sonst regulaere
        Kaskade. Die reine `assess_ice_risk` wird nur im Gutfall aufgerufen.

        Args:
            reading: Das zuletzt gepollte Reading (vom Poller). `None`, wenn der
                Poll fehlschlug (G1 nicht erreichbar / verworfen) -> Fail-safe.
            now: Bewertungszeitpunkt (UTC, zeitzonenbewusst).
            forecast_surface_temp_c: Optionale 30-min-T_s-Prognose (DTB-33/FA-06)
                fuer die GELB-Vorwarnung. `None` = keine Prognose -> ohne Einfluss
                auf die Bewertung. Nur im Gutfall (nicht stale/fault) wirksam.

        Returns:
            Das persistierte Assessment (mit vergebener `id`).

        Raises:
            ValueError: Wenn `now` nicht zeitzonenbewusst ist ODER ein gueltiges
                (nicht-stale, nicht-fault) Reading keine `id` traegt — dann hat der
                Poller die DTB-28-Persistenz-Invariante verletzt (sonst NULL-Snapshot).
            RepositoryError: Wenn die Assessment-Persistenz fehlschlaegt (der
                aufrufende Scheduler behandelt das fail-safe). Ein Fehler im
                Audit-Log bricht den Zyklus NICHT ab (best-effort, nur Log).
        """
        if now.tzinfo is None:
            raise ValueError("now muss zeitzonenbewusst sein (UTC)")

        stale_timeout_s = self._thresholds.datenqualitaet.stale_timeout_s

        # Hinweis: pydantic `model_copy(update=...)` validiert NICHT erneut (kein
        # max_length-Check). Die hier gesetzten driving_factor-Werte sind ausschliesslich
        # die DRIVING_FACTOR_*-Konstanten aus core.py und liegen garantiert <= 64 Zeichen;
        # neue Werte muessen diese Grenze ebenfalls einhalten (sonst 500 erst beim Serven).
        if reading is None:
            # Kein Reading -> kein reading_id moeglich (Fail-safe ohne Bezug).
            # RiskHysterese ticken (State-Desync-Schutz): UNKNOWN-Durchgang registrieren,
            # damit der naechste Gutfall sofort recoveryt statt auf der alten Stufe zu kleben.
            displayed = self._risk_hysterese.uebernimm_unknown(now)
            assessment = build_unknown_assessment("keine aktuellen Daten", now).model_copy(
                update={
                    "driving_factor": DRIVING_FACTOR_STALE,
                    "threshold_set_id": self._threshold_set_id,
                    "displayed_risk_level": displayed,
                }
            )
        elif reading.status is SensorStatus.FAULT:
            # Reading liegt vor (Poller hat persistiert) -> reading_id verknuepfen,
            # damit aus dem Snapshot nachvollziehbar bleibt, welches konkrete Reading
            # den Fail-safe ausgeloest hat (NF-05 / Audit-Traceability).
            displayed = self._risk_hysterese.uebernimm_unknown(now)
            assessment = build_unknown_assessment("sensor fault", now).model_copy(
                update={
                    "reading_id": reading.id,
                    "driving_factor": DRIVING_FACTOR_SENSOR_FAULT,
                    "threshold_set_id": self._threshold_set_id,
                    "displayed_risk_level": displayed,
                }
            )
        elif is_stale(reading, now, stale_timeout_s):
            displayed = self._risk_hysterese.uebernimm_unknown(now)
            assessment = build_unknown_assessment("stale (Messwert veraltet)", now).model_copy(
                update={
                    "reading_id": reading.id,
                    "driving_factor": DRIVING_FACTOR_STALE,
                    "threshold_set_id": self._threshold_set_id,
                    "displayed_risk_level": displayed,
                }
            )
        else:
            if reading.id is None:
                # Invariante: der Poller (DTB-28) MUSS das Reading persistiert haben,
                # bevor es bewertet wird. Sonst landet reading_id=NULL im Snapshot und
                # bricht die Audit-Traceability (NF-05) still -> laut scheitern statt
                # einen Snapshot ohne Reading-Bezug zu schreiben.
                raise ValueError(
                    "reading.id ist None: der Poller muss das Reading vor "
                    "assess_reading persistieren (DTB-28-Invariante)"
                )
            risk = assess_ice_risk(
                reading.surface_temp_c,
                reading.dew_point_c,
                self._thresholds,
                forecast_surface_temp_c=forecast_surface_temp_c,
            )
            # Anzeige-Hysterese (DTB-27): entprellte Stufe fuer die Ampel. risk (roh)
            # wird als risk_level persistiert (Alarm-Gen + Audit-Forensik); displayed
            # wird als displayed_risk_level gespeichert und vom Serve-Pfad ausgeliefert.
            # risk als roh_stufe durchreichen -> bewerten berechnet die Roh-Stufe nicht
            # erneut (assess_ice_risk laeuft pro Poll nur einmal, Review MEDIUM).
            displayed = self._risk_hysterese.bewerten(
                reading.surface_temp_c,
                reading.dew_point_c,
                self._thresholds,
                now,
                forecast_surface_temp_c=forecast_surface_temp_c,
                roh_stufe=risk,
            )
            delta_t = (
                None
                if reading.dew_point_c is None
                else reading.surface_temp_c - reading.dew_point_c
            )
            # DTB-66 + Hysterese: driving_factor/explanation erklaeren die ANGEZEIGTE
            # Stufe (`displayed`), nicht die rohe — sonst widerspricht der Text der
            # Ampel (z.B. Ampel ORANGE gehalten, aber Text "grenzwertig GELB"). Farbe
            # und Begruendung bleiben konsistent fuer den Operator. Die rohe Stufe steht
            # ueber risk_level weiterhin forensisch zur Verfuegung.
            driving_factor, explanation = derive_explanation(
                reading.surface_temp_c,
                reading.dew_point_c,
                self._thresholds,
                forecast_surface_temp_c,
                displayed,
                delta_t,
            )
            assessment = Assessment(
                ts=now,
                reading_id=reading.id,
                threshold_set_id=self._threshold_set_id,
                risk_level=risk,
                driving_factor=driving_factor,
                explanation=explanation,
                surface_temp_c=reading.surface_temp_c,
                dew_point_c=reading.dew_point_c,
                delta_t=delta_t,
                humidity_pct=reading.humidity_pct,
                forecast_surface_temp_c=forecast_surface_temp_c,
                displayed_risk_level=displayed,
            )

        assessment_id = self._assessment_repo.save(assessment)
        persisted = assessment.model_copy(update={"id": assessment_id})
        self._write_audit(persisted, now)
        return persisted

    def _write_audit(self, assessment: Assessment, now: datetime) -> None:
        """Schreibt das `assessment_made`-Ereignis (best-effort, fail-safe).

        Ein Audit-Fehler darf den sicherheitsrelevanten Bewertungs-Output NICHT
        blockieren -> nur loggen, nicht weiterwerfen (NF-01 vor NF-09).
        """
        try:
            self._audit_repo.append(
                AuditLogEntry(
                    ts=now,
                    event_type=AuditEventType.ASSESSMENT_MADE,
                    entity_type="assessment",
                    entity_id=assessment.id,
                    detail={"risk_level": str(assessment.risk_level)},
                )
            )
        except Exception:  # noqa: BLE001 - Audit ist best-effort; Zyklus nie crashen
            # logger.exception: Traceback mitloggen — bei einem geschluckten Audit-Fehler
            # (NF-09-Forensik) ist der Stack die einzige serverseitige Spur der Ursache.
            logger.exception("Audit-Eintrag (assessment_made) fehlgeschlagen")


def build_assessment_current(
    assessment: Assessment,
    reading: Reading,
    now: datetime,
    stale_timeout_s: float,
) -> AssessmentCurrent:
    """Baut den Wire-Response fuer GET /v1/assessment/current mit Serve-Zeit-NF-01.

    Erzwingt den Fail-safe ZUM ABFRAGEZEITPUNKT (nicht nur zur Bewertungszeit):
    ist das zugrunde liegende Reading inzwischen veraltet ODER meldet der Sensor
    `fault`, wird `risk_level=unknown` ausgeliefert (nie GRUEN) und die
    Messwerte werden genullt — unabhaengig davon, was gespeichert ist.

    Der Aufrufer (DTB-43) MUSS den Fall "noch gar keine Daten" (kein Assessment
    oder kein Reading) VOR diesem Aufruf mit HTTP 503 abfangen — hier wird ein
    vorhandenes Reading vorausgesetzt (fuer `measured_at`, das auf 200 immer gesetzt ist).

    Args:
        assessment: Zuletzt persistierte Bewertung.
        reading: Zuletzt gespeichertes Reading desselben Sensors (Aktualitaets-Basis).
        now: Abfragezeitpunkt (UTC, zeitzonenbewusst).
        stale_timeout_s: Stale-Grenze in Sekunden (aus Config, NF-05).

    Returns:
        Contract-konformer AssessmentCurrent-Response.

    Raises:
        ValueError: Wenn `reading` None ist — der Aufrufer (DTB-43) muss den
            No-Data-Fall VOR diesem Aufruf mit HTTP 503 behandeln.
    """
    if reading is None:
        # Vertrag explizit absichern: laut scheitern statt spaeter ein AttributeError
        # tief im Stack (reading.status / reading.measured_at), wenn beim Einkommentieren
        # des DTB-43-Endpoints der None-Pfad vergessen wird.
        raise ValueError(
            "build_assessment_current: reading darf nicht None sein "
            "(Aufrufer muss den No-Data-Fall mit 503 behandeln)"
        )
    stale = is_stale(reading, now, stale_timeout_s)
    sensor_status = reading.status
    fault = sensor_status is SensorStatus.FAULT
    # Serve-Zeit-Kohaerenz (NF-01): das Assessment MUSS das aktuelle Reading bewertet haben.
    # Bei partiellem DB-Fehler (Reading gespeichert, Assessment-INSERT gescheitert) oder einem
    # Race kann get_latest() ein ALTES Assessment (evtl. GRUEN) mit einem FRISCHEREN Reading
    # paaren -> die gespeicherte Bewertung gilt nicht fuer dieses Reading -> Fail-safe unknown.
    # Nur pruefen, wenn beide ids vorliegen (Produktion: immer; Test-/Legacy-Assets ohne id
    # sollen den Kohaerenz-Check nicht faelschlich ausloesen).
    incoherent = (
        assessment.reading_id is not None
        and reading.id is not None
        and assessment.reading_id != reading.id
    )

    if stale or fault or incoherent:
        # Alle zutreffenden Gruende nennen (Observability fuer den Operator) — sensor_status
        # traegt fault zwar strukturiert, explanation soll den Fail-safe vollstaendig erklaeren.
        reason = " + ".join(
            label
            for label, active in (
                ("stale", stale),
                ("sensor fault", fault),
                ("assessment/reading mismatch", incoherent),
            )
            if active
        )
        # DTB-66: driving_factor spiegelt den gravierendsten Fail-safe-Grund.
        # Fault (Sensorfehler = Ursache) > Stale (oft Folge) > Kohaerenz-Bruch (Datenlage).
        fail_driving_factor = (
            DRIVING_FACTOR_SENSOR_FAULT
            if fault
            else DRIVING_FACTOR_STALE
            if stale
            else DRIVING_FACTOR_SENSOR_DATA
        )
        return AssessmentCurrent(
            risk_level=RiskLevel.UNKNOWN,
            driving_factor=fail_driving_factor,
            explanation=f"Fail-safe: {reason}"[:MAX_EXPLANATION_LEN],
            surface_temp_c=None,
            dew_point_c=None,
            delta_t=None,
            humidity_pct=None,
            # Kontextfelder folgen der Messwert-Nullung (Fail-safe, NF-01): keine veralteten
            # Wind-/Feuchtewerte am Live-Snapshot, wenn der Zustand unknown ist.
            surface_moisture_pct=None,
            wind_speed_ms=None,
            forecast_surface_temp_c=None,  # NF-01: keine Prognose auf stale/fault
            measured_at=reading.measured_at,
            assessed_at=assessment.ts,
            is_stale=stale,
            sensor_status=sensor_status,
        )

    # Aktuell und Sensor ok -> die persistierte Bewertung gilt unveraendert.
    # Serve-Ampel = entprellte Stufe (DTB-27 Anzeige-Hysterese). Fallback auf risk_level,
    # falls das Assessment noch kein displayed_risk_level traegt (Legacy-/Test-Assets vor
    # der Hysterese-Einfuehrung) -> konservativ roh nehmen statt None ans Wire zu leaken.
    served_risk = assessment.displayed_risk_level
    if served_risk is None:
        served_risk = assessment.risk_level
    return AssessmentCurrent(
        risk_level=served_risk,
        driving_factor=assessment.driving_factor,
        explanation=assessment.explanation,
        surface_temp_c=assessment.surface_temp_c,
        dew_point_c=assessment.dew_point_c,
        delta_t=assessment.delta_t,
        humidity_pct=assessment.humidity_pct,
        # Kontextfelder (Contract v1.2) aus dem aktuellen Reading — nur Speicher/Anzeige,
        # nicht bewertungsrelevant. Auf dem Gut-Pfad ist `reading` das bewertete Reading.
        surface_moisture_pct=reading.surface_moisture_pct,
        wind_speed_ms=reading.wind_speed_ms,
        forecast_surface_temp_c=assessment.forecast_surface_temp_c,
        measured_at=reading.measured_at,
        assessed_at=assessment.ts,
        is_stale=False,
        sensor_status=sensor_status,
    )
