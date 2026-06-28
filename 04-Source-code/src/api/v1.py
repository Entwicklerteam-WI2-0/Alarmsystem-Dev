"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03). Aktuell: `GET /v1/thresholds`
(DTB-62) und `GET /v1/readings` (DTB-34).
Alle Endpoints hier sind **rein lesend** (RB-01-neutral).
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from src.api.broadcaster import StreamCapacityError, sse_alarm_frames
from src.api.responses import NO_STORE_HEADERS, service_unavailable, unprocessable_entity
from src.api.runtime import Runtime, get_runtime
from src.api.security import require_api_key
from src.config.constants import DEFAULT_SENSOR_ID
from src.config.loader import ConfigError, Thresholds, parse_thresholds
from src.model.enums import AlarmState, AuditEventType
from src.model.schemas import (
    AlarmResponse,
    AuditLogEntry,
    Error,
    ReadingResponse,
    ThresholdSet,
    ThresholdUpdateRequest,
)
from src.storage.repository import RepositoryError

logger = logging.getLogger(__name__)

# Kein Router-weiter Tag: jeder Endpoint deklariert seinen Ressourcen-Tag selbst
# (wie assessment/current -> "Assessment" in main.py), damit die FastAPI-Auto-Docs
# (/docs, /openapi.json) dieselbe Gruppierung zeigen wie die eingefrorene openapi.yaml.
router = APIRouter(prefix="/v1")


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


@router.get(
    "/readings",
    response_model=list[ReadingResponse],
    summary="Historie der Messwerte lesen",
    tags=["Readings"],
    responses={
        400: {
            "model": Error,
            "description": "Ungueltige Query-Parameter (z. B. from nach to).",
        },
        503: {
            "model": Error,
            "description": "G2 (noch) nicht lieferfaehig (Runtime nicht bereit / DB-Ausfall).",
        },
    },
)
def read_readings(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    response: Response,
    from_dt: Annotated[
        datetime | None,
        Query(
            alias="from",
            description="Untere Zeitgrenze (ISO-8601, UTC), inklusiv.",
        ),
    ] = None,
    to_dt: Annotated[
        datetime | None,
        Query(
            alias="to",
            description="Obere Zeitgrenze (ISO-8601, UTC), inklusiv.",
        ),
    ] = None,
    sensor_id: Annotated[
        str,
        Query(
            description="Sensor-ID; Default: einziger aktiver Sensor.",
            min_length=1,
            max_length=64,
        ),
    ] = DEFAULT_SENSOR_ID,
    limit: Annotated[
        int,
        Query(description="Maximale Anzahl Eintraege.", ge=1, le=1000),
    ] = 100,
    offset: Annotated[
        int,
        Query(description="Anzahl zu ueberspringender Zeilen.", ge=0, le=100_000),
    ] = 0,
    order: Annotated[
        Literal["asc", "desc"],
        Query(description="Sortierung nach measured_at."),
    ] = "desc",
) -> list[ReadingResponse] | JSONResponse:
    """Liefert die Messwert-Historie fuer G3 (DTB-34, FA-03).

    Rein lesend (RB-01-neutral). Zeitstempel muessen zeitzonenbewusst sein;
    `from` darf nicht nach `to` liegen. Bei Persistenzfehlern wird fail-safe
    503 im Contract-Format `Error {code, message}` gemeldet.
    """
    response.headers.update(NO_STORE_HEADERS)

    try:
        readings = runtime.reading_repo.get_between(
            sensor_id=sensor_id,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=limit,
            offset=offset,
            order=order,
        )
        # Domain->Wire-Mapping bewusst INNERHALB des try: Schluege es bei unerwartetem
        # Drift fehl (z. B. id=None, Schema-Drift nach Migration, korrupte DB-Zeile in
        # _row_to_reading), propagierte sonst ein roher 500 und braeche den
        # `Error {code, message}`-Contract (NF-01).
        readings_wire = [ReadingResponse(**reading.model_dump()) for reading in readings]
    except ValidationError:
        # WICHTIG: In Pydantic v2 (>=2.x) IST ValidationError eine Subklasse von ValueError
        # -> dieser Handler MUSS vor `except ValueError` stehen, sonst wuerde ein
        # serverseitiger Mapping-/Persistenz-Drift faelschlich als 400 (Client-Fehler) mit
        # der ueberlangen Roh-Pydantic-Message ausgegeben (die zudem Error.message > 512
        # sprengt und einen Folge-500 ausloeste). Drift ist serverseitig -> fail-safe 503,
        # ohne interne Details preiszugeben (NF-01).
        logger.exception("Domain->Wire-Mapping der Readings-Historie fehlgeschlagen (Drift?).")
        return service_unavailable("G2 momentan nicht lieferfaehig.")
    except ValueError as exc:
        # Ungueltige Parameter (from nach to, naive/Non-UTC Zeitstempel) -> 400.
        # Debug-Log fuer die Diagnose wiederkehrender Client-400 (z. B. G3 sendet
        # naive/Non-UTC-Zeitstempel) — die Ursache steht sonst nirgends serverseitig.
        logger.debug("readings: ungueltige Query-Parameter: %s", exc)
        return JSONResponse(
            status_code=400,
            content=Error(code="BAD_REQUEST", message=str(exc)).model_dump(),
        )
    except RepositoryError as exc:
        # DB-Ausfall -> 503 (Fail-safe, NF-01-Geist). Die gewrappte Ursache am
        # API-Rand loggen (analog assessment/current), sonst bleibt ein DB-Ausfall
        # auf diesem Endpoint ohne API-seitige Spur.
        logger.error("readings: Persistenz nicht verfuegbar: %s", exc)
        return service_unavailable("G2 momentan nicht lieferfaehig.")
    except Exception:  # noqa: BLE001 - letzter Fail-safe: JEDER Fehlerpfad liefert
        # `Error {code, message}` (Contract), nie ein roher 500 mit {detail: ...}.
        # Die volle Ursache bleibt im Log (logger.exception) erhalten (NF-01).
        logger.exception("Unerwarteter Fehler beim Lesen der Readings-Historie.")
        return service_unavailable("G2 momentan nicht lieferfaehig.")

    return readings_wire


@router.get(
    "/alarms",
    response_model=list[AlarmResponse],
    summary="Zustands-Abfrage der Alarme (Resync, kein Entdeckungs-Poll)",
    tags=["Alarms"],
    responses={
        400: {
            "model": Error,
            "description": "Ungueltiger state-Filter.",
        },
        503: {
            "model": Error,
            "description": "G2 (noch) nicht lieferfaehig (Runtime nicht bereit / DB-Ausfall).",
        },
    },
)
def list_alarms(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    response: Response,
    state: Annotated[
        AlarmState | None,
        Query(
            description=(
                "Auf einen Alarm-Zustand filtern (active|acknowledged|cleared). "
                "Ohne Angabe: alle OFFENEN Alarme (active + acknowledged). Ein "
                "ungueltiger Wert -> 400 (globaler Request-Validation-Handler)."
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(description="Maximale Anzahl zurueckgegebener Alarme.", ge=1, le=500),
    ] = 100,
) -> list[AlarmResponse] | JSONResponse:
    """Liefert Alarme als Resync-Backstop fuer G3 (DTB-31, E-37).

    Zustands-Abfrage fuer Initial-Load + Resync nach SSE-Disconnect -- KEIN
    Entdeckungs-Poll (Live-Alarme kommen ueber GET /v1/alarms/stream). Rein lesend
    (RB-01-neutral): kein Zustandswechsel, kein Aktor.

    Ohne `state`-Filter werden die OFFENEN Alarme (active + acknowledged) geliefert, damit
    nach einem Disconnect auch bereits quittierte, aber noch nicht beendete Alarme in der
    G3-Ansicht bleiben. Bei Persistenzfehlern wird fail-safe 503 im Contract-Format
    `Error {code, message}` gemeldet (NF-01).

    `state` ist als `AlarmState`-Enum typisiert (matcht das frozen openapi.yaml-Schema
    `$ref AlarmState`). Ein ungueltiger Wert wird vom globalen RequestValidationError-
    Handler contract-konform als `400 Error{code, message}` abgebildet (Query-Fehler =
    400, Contract D) -- nicht als FastAPI-Default-422.
    """
    response.headers.update(NO_STORE_HEADERS)

    try:
        alarms = runtime.alarm_repo.get_alarms(state=state, limit=limit)
        # Domain->Wire-Mapping bewusst INNERHALB des try (analog readings): ein unerwarteter
        # Drift (z. B. id=None) propagierte sonst als roher 500 und braeche den
        # Error{code,message}-Contract (NF-01).
        alarms_wire = [AlarmResponse(**alarm.model_dump()) for alarm in alarms]
    except ValidationError:
        # Serverseitiger Mapping-/Schema-Drift -> fail-safe 503, ohne interne Details (NF-01).
        logger.exception("Domain->Wire-Mapping der Alarme fehlgeschlagen (Drift?).")
        return service_unavailable("G2 momentan nicht lieferfaehig.")
    except RepositoryError as exc:
        # DB-Ausfall -> 503 (Fail-safe, NF-01). Ursache am API-Rand loggen.
        logger.error("alarms: Persistenz nicht verfuegbar: %s", exc)
        return service_unavailable("G2 momentan nicht lieferfaehig.")
    except Exception:  # noqa: BLE001 - letzter Fail-safe: JEDER Fehlerpfad liefert
        # Error{code,message} (Contract), nie ein roher 500 mit {detail}. Volle Ursache
        # bleibt im Log (logger.exception) erhalten (NF-01).
        logger.exception("Unerwarteter Fehler beim Lesen der Alarme.")
        return service_unavailable("G2 momentan nicht lieferfaehig.")

    return alarms_wire


# SSE-Antwortheader (DTB-61): no-store (Echtzeit-Sicherheitsnaht, kein Cache eines
# ueberholten Stream-Zustands) und X-Accel-Buffering:no (schaltet das Response-Buffering
# eines Reverse-Proxys wie nginx fuer SSE ab -> Events erreichen G3 sofort statt blockweise).
# KEIN "Connection: keep-alive": in HTTP/1.1 ohnehin Default (redundant) und in HTTP/2 ein
# verbotener hop-by-hop-Header (RFC 9113 §8.2.2). Die SSE-Verbindung bleibt durch den
# offenen Body-Stream offen, nicht durch diesen Header.
_SSE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Accel-Buffering": "no",
}

# Obergrenze fuer den geloggten Last-Event-ID-Wert (Diagnose reicht; verhindert ueberlange
# client-kontrollierte Log-Zeilen).
_MAX_LOGGED_HEADER_LEN = 64


def _sanitize_header_value(value: str) -> tuple[str, bool]:
    """Bereinigt einen Headerwert + meldet, OB nicht-druckbare Zeichen entfernt wurden.

    Returns `(sanitized, had_non_printable)` in EINEM Scan: der bereinigte Log-Wert UND das
    Injection-Verdacht-Flag des Aufrufers teilen sich dieselbe Iteration (statt den Header
    zweimal zu durchlaufen).

    Schutz gegen Log-Injection/-Forging (NF-09 Log-Integritaet): ein eingeschmuggelter
    Zeilenumbruch ODER Unicode-Zeilentrenner (U+2028/U+2029) im (von G3 gesendeten)
    Last-Event-ID-Header koennte sonst eine gefaelschte/verschleierte Log-Zeile erzeugen.
    Gefiltert wird per str.isprintable() (entfernt CR/LF, Tabs, C0/C1-Controls, Zero-Width);
    normaler Text + Leerzeichen bleiben. Geloggt wird nur der bereinigte, begrenzte Wert.
    `had_non_printable` ist True, sobald IRGENDEIN Zeichen entfernt wurde (an jeder Position) —
    eine blosse Laengen-Kuerzung eines sauberen Werts loest es NICHT aus (kein False-Positive).
    """
    printable = [ch for ch in value if ch.isprintable()]
    return "".join(printable)[:_MAX_LOGGED_HEADER_LEN], len(printable) != len(value)


@router.get(
    "/alarms/stream",
    summary="Live-Alarm-Stream (Server-Sent Events)",
    tags=["Alarms"],
    # Union-Rueckgabe (StreamingResponse | JSONResponse) ist kein Pydantic-Response-Model;
    # FastAPI soll daraus KEINS ableiten (200 = SSE-Stream, 503 = Error sind in `responses`
    # dokumentiert). Ohne dies wirft FastAPI beim Start einen FastAPIError.
    response_model=None,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Offener SSE-Stream; jedes Event traegt einen Alarm als JSON.",
        },
        503: {
            "model": Error,
            "description": (
                "G2 (noch) nicht lieferfaehig (Runtime nicht bereit) ODER Stream-Kapazitaet "
                "erreicht (zu viele gleichzeitige Verbindungen)."
            ),
        },
    },
)
async def stream_alarms(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    request: Request,
) -> StreamingResponse | JSONResponse:
    """Pusht ausgeloeste Alarme live an G3 (E-37) — kein Polling, kein Aktor (RB-01).

    Bei voller Stream-Kapazitaet (zu viele gleichzeitige Verbindungen) wird die neue
    Verbindung mit 503 (`Error {code, message}`) abgewiesen, statt unbegrenzt Speicher zu
    binden — rein abweisend, kein Aktor.

    Der Client haelt eine offene Verbindung; G2 sendet pro neuem Alarm ein SSE-Event
    (`id:` = Alarm-ID fuer Reconnect via Last-Event-ID, `data:` = Alarm-JSON) und alle
    ~15 s einen `:keep-alive`-Heartbeat. Verpasste Events nach einem Reconnect holt G3
    ueber den Resync `GET /v1/alarms` (DTB-31, Sicherheits-Backstop) — der Stream selbst
    puffert keine Historie.

    `reserve()` legt das Abo synchron + kapazitaetsgeprueft an; `release()` baut es im
    `_frames`-finally beim Verbindungsende wieder ab; `request.is_disconnected` beendet den
    Generator, sobald der Client geht.

    Reconnect: das `id:`-Feld jedes Frames IST der Reconnect-Mechanismus — der Client
    sendet beim Wiederverbinden den zuletzt gesehenen Wert als `Last-Event-ID`-Header.
    G2 puffert bewusst KEINE Historie (kein Replay); verpasste Alarme holt G3 ueber den
    Resync `GET /v1/alarms` (DTB-31). Der eingehende Header wird daher nur protokolliert
    (Diagnose), nicht zum Nachliefern verwendet.
    """
    last_event_id = request.headers.get("last-event-id")
    if last_event_id:
        sanitized, had_non_printable = _sanitize_header_value(last_event_id)
        if had_non_printable:
            # Nicht-druckbare Zeichen im client-kontrollierten Header -> moeglicher Injection-/
            # Log-Forging-Versuch (G3-Bug oder MitM). Fuer proaktives Security-Monitoring als
            # WARNING sichtbar machen (NF-09-Geist), statt nur still zu bereinigen.
            logger.warning(
                "Last-Event-ID enthielt nicht-druckbare Zeichen — moeglicher Injection-Versuch."
            )
        logger.info(
            "SSE-Reconnect mit Last-Event-ID=%s — G3 sollte via GET /v1/alarms resyncen "
            "(DTB-31); G2 liefert keine Historie nach.",
            sanitized,
        )

    broadcaster = runtime.alarm_broadcaster
    try:
        # Abo SYNCHRON reservieren (race-frei) -> bei voller Kapazitaet kann der Endpoint
        # noch contract-konform mit 503 antworten, BEVOR ein StreamingResponse (200) beginnt.
        queue = broadcaster.reserve()
    except StreamCapacityError as exc:
        logger.warning("SSE-Stream-Kapazitaet erreicht — Verbindung mit 503 abgewiesen: %s", exc)
        return service_unavailable("Stream-Kapazitaet erreicht; bitte spaeter erneut verbinden.")

    async def _frames() -> AsyncGenerator[str, None]:
        try:
            async for frame in sse_alarm_frames(queue, request.is_disconnected):
                yield frame
        finally:
            # Abo am Verbindungsende abmelden (Kapazitaet freigeben, Leak verhindern).
            # Invarianten-verletzende Alarme (id=None) filtert bereits publish() am Ingress;
            # ein _frame()-raise bliebe hier defensiv und wuerde via finally sauber released.
            broadcaster.release(queue)

    try:
        return StreamingResponse(_frames(), media_type="text/event-stream", headers=_SSE_HEADERS)
    except Exception:  # noqa: BLE001 - akademisch (StreamingResponse wirft praktisch nie)
        # Reservierten Slot freigeben, falls die Response-Konstruktion scheitert: der
        # _frames-finally liefe nie (der Generator startet nicht) -> sonst dauerhaft belegt.
        # Awareness (PR-Review): sammelt asyncios Async-Gen-Finalizer den nie gestarteten
        # _frames-Generator spaeter via aclose() ein, koennte dessen finally erneut release()
        # rufen. Das ist sicher, weil release() idempotent ist (s. AlarmBroadcaster.release) —
        # die Idempotenz ist hier der bewusste Sicherheitsgurt, keine zufaellige Annahme.
        broadcaster.release(queue)
        raise
