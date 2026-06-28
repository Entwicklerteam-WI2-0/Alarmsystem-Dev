"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03). Aktuell: `GET /v1/thresholds`
(DTB-62) — liefert die aktuell konfigurierten Schwellenwerte fuer das G3-Menue.
Alle Endpoints hier sind **rein lesend** (RB-01-neutral): kein Aktor, keine
Runway-Steuerung.
"""

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from src.api.responses import NO_STORE_HEADERS, service_unavailable, unprocessable_entity
from src.api.runtime import Runtime, get_runtime
from src.api.security import require_api_key
from src.config.loader import ConfigError, Thresholds, parse_thresholds
from src.model.enums import AuditEventType
from src.model.schemas import AuditLogEntry, Error, ThresholdSet, ThresholdUpdateRequest
from src.storage import RepositoryError

# Kein Router-weiter Tag: jeder Endpoint deklariert seinen Ressourcen-Tag selbst
# (wie assessment/current -> "Assessment" in main.py), damit die FastAPI-Auto-Docs
# (/docs, /openapi.json) dieselbe Gruppierung zeigen wie die eingefrorene openapi.yaml.
router = APIRouter(prefix="/v1")

logger = logging.getLogger(__name__)


def get_thresholds(runtime: Annotated[Runtime, Depends(get_runtime)]) -> Thresholds:
    """Aktive Schwellenwerte = die zur Laufzeit geladenen (`runtime.thresholds`).

    Bewusst KEIN Disk-Read pro Request: der Endpoint spiegelt exakt die Schwellen, die
    die Bewertungslogik gerade verwendet (eine Quelle der Wahrheit, Konsistenz mit
    assessment/current) — statt einer Datei, die von der laufenden Bewertung abweichen
    koennte. Geladen wird genau einmal beim Start (`build_runtime` -> `load_thresholds`);
    eine geaenderte Config greift nach einem kontrollierten Neustart/Reload (NF-07).
    Eigene Dependency, damit Tests sie via `app.dependency_overrides` ersetzen koennen
    und der Endpoint nie hardcodiert. Bei nicht bereitem Runtime (z. B. Config beim Start
    nicht ladbar) meldet `get_runtime` fail-safe `RuntimeNotReadyError` -> 503.
    """
    return runtime.thresholds


@router.get(
    "/thresholds",
    response_model=Thresholds,
    summary="Aktuelle Schwellenwerte lesen",
    tags=["Thresholds"],
    responses={
        503: {
            "model": Error,
            "description": "G2 (noch) nicht lieferfaehig (Runtime nicht bereit).",
        }
    },
)
def read_thresholds(
    thresholds: Annotated[Thresholds, Depends(get_thresholds)],
    response: Response,
) -> Thresholds:
    """Liefert die aktuell konfigurierten Schwellenwerte (NF-05) fuer G3.

    Rein lesend (RB-01-neutral). Werte kommen aus dem zur Laufzeit geladenen
    Runtime-Graph (DTB-15); Aendern erfolgt spaeter ueber einen separaten,
    Auth-geschuetzten Endpoint (NF-07).

    `Cache-Control: no-store`: Schwellen sind die Kalibrierung eines Fail-safe-Systems.
    Ein Proxy/Browser, der ueberholte Schwellen ausliefert, wuerde G3 einen falschen
    Betriebspunkt anzeigen (NF-01-Geist). Eine Konvention mit `assessment/current`.
    """
    response.headers.update(NO_STORE_HEADERS)
    return thresholds


@router.post(
    "/thresholds",
    status_code=201,
    dependencies=[Depends(require_api_key)],
    response_model=ThresholdSet,
    summary="Schwellenwerte versioniert anlegen (Auth, nicht-idempotent)",
    tags=["Thresholds"],
    responses={
        401: {"model": Error, "description": "Kein/ungueltiger API-Key (NF-07)."},
        422: {"model": Error, "description": "Ungueltige Schwellen-Konfiguration."},
        503: {
            "model": Error,
            "description": "Schreibzugriff nicht konfiguriert ODER Persistenz nicht verfuegbar.",
        },
    },
)
def create_threshold_version(
    payload: ThresholdUpdateRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> ThresholdSet | JSONResponse:
    """Legt einen neuen, versionierten Schwellensatz an (DTB-63, NF-07/NF-05).

    Bewusst `create_…` statt `update_…`: der Endpoint ist append-only (INSERT/
    Supersession per `valid_from`, nie UPDATE), passend zur OpenAPI-operationId
    `createThresholdVersion`.

    Auth-geschuetzt (`Authorization: Bearer <key>`, `require_api_key`). Schreibt den
    Satz append-only als neuen `threshold_set` (Supersession per `valid_from`, DTB-54)
    und in DERSELBEN Transaktion den `threshold_changed`-Audit-Eintrag (NF-09).

    Reload-Semantik (bewusste Architektur-Entscheidung): der neue Satz wird beim
    naechsten kontrollierten Reload/Neustart aktiv — die laufende Bewertung nutzt bis
    dahin die bisherigen Schwellen (kein Live-Swap des Runtime-Graphen). `201` traegt
    den angelegten Satz.

    RB-01-neutral: aendert nur die Entscheidungs-Parameter, kein Aktor/keine Freigabe.
    """
    # Fehler-Muster bewusst lokal (nicht ueber app.exception_handler): beide Fehlerquellen
    # dieses Endpoints werden hier auf je EINE Contract-Antwort abgebildet — ConfigError ->
    # 422 (Client), RepositoryError -> 503 (Server) — und bleiben so co-lokal sichtbar. Ein
    # globaler Handler fuer die endpoint-spezifische 422-Meldung waere Indirektion ohne
    # Nutzen; RepositoryError wird zudem auch anderswo (assessment/current in main.py) lokal
    # pro Endpoint abgebildet -> ein globaler Handler wuerde dort Verhalten aendern.
    #
    # Volle fachliche Validierung ueber den kanonischen Loader — identische Regeln wie
    # die Datei-Config (Pflicht-Sektionen, endliche Zahlen, Cross-Section-Invarianten).
    # Ungueltiger Body -> 422 (Client-Fehler, der Body ist schuld).
    try:
        validated = parse_thresholds(payload.thresholds)
    except ConfigError as exc:
        return unprocessable_entity(f"Ungueltige Schwellen-Konfiguration: {exc}")

    now = datetime.now(UTC)
    # Kanonische, validierte Form speichern (verwirft Kommentar-/Unbekannt-Keys); genau
    # diese Struktur laedt parse_thresholds beim naechsten Reload wieder ein.
    threshold_set = ThresholdSet(
        name=payload.name,
        params=asdict(validated),
        valid_from=now,
        changed_by=payload.changed_by,
    )
    audit_entry = AuditLogEntry(
        ts=now,
        event_type=AuditEventType.THRESHOLD_CHANGED,
        entity_type="threshold_set",
        actor=payload.changed_by,
        detail={"name": payload.name},
    )
    try:
        new_id = runtime.threshold_set_repo.append(threshold_set, audit_entry)
    except RepositoryError as exc:
        # Persistenz-/DB-Ausfall: Detail server-seitig loggen, nach aussen generisch (Contract D).
        logger.error("Schwellen-Update fehlgeschlagen: %s", exc)
        return service_unavailable("G2 momentan nicht lieferfaehig.")

    return threshold_set.model_copy(update={"id": new_id})
