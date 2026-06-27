"""Composition-Root des G2-Backends (DTB-64).

`build_runtime()` baut den Dependency-Graph einer laufenden Instanz. Als eigenes
Modul abgelegt, damit sowohl `main.py` (Lifespan/Scheduler) als auch
`src/api/v1.py` (Runtime-Reload nach Config-Update) ihn importieren koennen —
ohne zirkulaeren Import (Router -> Composition Root).
"""

from __future__ import annotations

import os

from src.alarm.hysterese import AlarmHysterese
from src.alarm.service import AlarmGenerator
from src.api.runtime import Runtime
from src.assessment import AssessmentService
from src.config.loader import load_thresholds
from src.ingest.poller import Poller
from src.storage import MySqlAssessmentRepository, MySqlAuditRepository, ReadingRepository
from src.storage.acknowledgement_repository import MySqlAcknowledgementRepository
from src.storage.alarm_repository import MySqlAlarmRepository

# Bewusster Default: http:// im abgeschlossenen Projekt-/Intranet (G1 ist ein
# Prototyp ohne TLS). Fuer realen Betrieb HTTPS NICHT hier hart erzwingen — ein
# https://-Default wuerde die Verbindung zu einem HTTP-only-G1 brechen (eingefrorene
# Naht). Stattdessen pro Umgebung per Env umstellen: G1_BASE_URL=https://g1-sensorik.local
# (dokumentiert in .env.example). Architektenentscheidung, falls HTTPS-Default + HTTP-Opt-in
# gewuenscht wird.
_DEFAULT_G1_BASE_URL = "http://g1-sensorik.local"


def build_runtime() -> Runtime:
    """Baut den DI-Graph (ohne DB/G1 zu kontaktieren — Repos verbinden erst pro Query)."""
    thresholds = load_thresholds()
    reading_repo = ReadingRepository()
    assessment_repo = MySqlAssessmentRepository()
    audit_repo = MySqlAuditRepository()
    poller = Poller(
        base_url=os.environ.get("G1_BASE_URL", _DEFAULT_G1_BASE_URL),
        repository=reading_repo,
        data_quality_thresholds=thresholds.datenqualitaet,
        plausibility_thresholds=thresholds.plausibilitaet,
    )
    service = AssessmentService(thresholds, assessment_repo, audit_repo)
    # DTB-27: Alarm-Generierung als Konsument der Bewertung. AlarmHysterese ist pro Sensor
    # zustandsbehaftet (On-Delay) -> gehoert in den langlebigen DI-Graph (eine Instanz je
    # laufende Instanz; aktuell genau ein Sensor). Audit-Log wird mit dem Service geteilt.
    alarm_repo = MySqlAlarmRepository()
    alarm_generator = AlarmGenerator(AlarmHysterese(thresholds.hysterese), alarm_repo, audit_repo)
    ack_repo = MySqlAcknowledgementRepository()
    return Runtime(
        thresholds=thresholds,
        reading_repo=reading_repo,
        assessment_repo=assessment_repo,
        audit_repo=audit_repo,
        ack_repo=ack_repo,
        poller=poller,
        service=service,
        alarm_generator=alarm_generator,
    )
