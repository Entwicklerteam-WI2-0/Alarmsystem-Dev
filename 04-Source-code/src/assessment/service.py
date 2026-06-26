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

import logging
from datetime import datetime

from src.assessment.core import assess_ice_risk
from src.assessment.failsafe import build_unknown_assessment, is_stale
from src.config.loader import Thresholds
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
        assessment_repo: AssessmentRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._thresholds = thresholds
        self._assessment_repo = assessment_repo
        self._audit_repo = audit_repo

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

        if reading is None:
            # Kein Reading -> kein reading_id moeglich (Fail-safe ohne Bezug).
            assessment = build_unknown_assessment("keine aktuellen Daten", now)
        elif reading.status is SensorStatus.FAULT:
            # Reading liegt vor (Poller hat persistiert) -> reading_id verknuepfen,
            # damit aus dem Snapshot nachvollziehbar bleibt, welches konkrete Reading
            # den Fail-safe ausgeloest hat (NF-05 / Audit-Traceability).
            assessment = build_unknown_assessment("sensor fault", now).model_copy(
                update={"reading_id": reading.id}
            )
        elif is_stale(reading, now, stale_timeout_s):
            assessment = build_unknown_assessment(
                "stale (Messwert veraltet)", now
            ).model_copy(update={"reading_id": reading.id})
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
            delta_t = (
                None
                if reading.dew_point_c is None
                else reading.surface_temp_c - reading.dew_point_c
            )
            assessment = Assessment(
                ts=now,
                reading_id=reading.id,
                risk_level=risk,
                # threshold_set_id bleibt bewusst None: der aktuelle Loader (DTB-15)
                # traegt keine Schwellensatz-Referenz (nur Sektionen), der geltende
                # Satz ist strukturell noch nicht belegbar. Die DB-Spalte (FK auf
                # threshold_set) + INSERT/SELECT sind vorbereitet; die audit-feste
                # Traceability bei Schwellen-Aenderungen (NF-05) zieht DTB-65 nach.
                # driving_factor/explanation: optionale Klartext-Felder; reichern
                # DTB-27 (Alarm-Begruendung) bzw. ein Folge-Task an. TODO DTB-64+.
                surface_temp_c=reading.surface_temp_c,
                dew_point_c=reading.dew_point_c,
                delta_t=delta_t,
                humidity_pct=reading.humidity_pct,
                forecast_surface_temp_c=forecast_surface_temp_c,
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
        except Exception as exc:  # noqa: BLE001 - Audit ist best-effort; Zyklus nie crashen
            logger.error("Audit-Eintrag (assessment_made) fehlgeschlagen: %s", exc)


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

    if stale or fault:
        # Beide Gruende nennen, wenn beide zutreffen (Observability fuer den
        # Operator) — sensor_status traegt fault zwar strukturiert, explanation
        # soll den Fail-safe aber vollstaendig erklaeren.
        reason = " + ".join(
            label for label, active in (("stale", stale), ("sensor fault", fault)) if active
        )
        return AssessmentCurrent(
            risk_level=RiskLevel.UNKNOWN,
            driving_factor=None,
            explanation=f"Fail-safe: {reason}",
            surface_temp_c=None,
            dew_point_c=None,
            delta_t=None,
            humidity_pct=None,
            measured_at=reading.measured_at,
            assessed_at=assessment.ts,
            is_stale=stale,
            sensor_status=sensor_status,
        )

    # Aktuell und Sensor ok -> die persistierte Bewertung gilt unveraendert.
    return AssessmentCurrent(
        risk_level=assessment.risk_level,
        driving_factor=assessment.driving_factor,
        explanation=assessment.explanation,
        surface_temp_c=assessment.surface_temp_c,
        dew_point_c=assessment.dew_point_c,
        delta_t=assessment.delta_t,
        humidity_pct=assessment.humidity_pct,
        measured_at=reading.measured_at,
        assessed_at=assessment.ts,
        is_stale=False,
        sensor_status=sensor_status,
    )
