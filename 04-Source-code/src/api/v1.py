"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03): `GET /v1/thresholds` (DTB-62),
`GET /v1/alarms/stream` (DTB-61, SSE) und `POST /v1/alarms/{id}/ack` (DTB-24,
Quittierung). Alle sind **RB-01-neutral**: der ack-Endpoint schreibt zwar (Zustand
`active -> acknowledged` + Audit), ist aber reine UI-/Audit-Quittierung — KEIN Aktor,
keine Runway-Freigabe/-Sperre.
"""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from src.api.broadcaster import StreamCapacityError, sse_alarm_frames
from src.api.responses import (
    ALARM_ALREADY_ACKNOWLEDGED_CODE,
    BAD_REQUEST_CODE,
    NO_STORE_HEADERS,
    NOT_FOUND_CODE,
    error_response,
    service_unavailable,
)
from src.api.runtime import Runtime, get_runtime
from src.config.loader import Thresholds
from src.model.schemas import Acknowledgement, AckRequest, Error
from src.storage.acknowledgement_repository import (
    AlarmNotAcknowledgeableError,
    AlarmNotFoundError,
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


@router.post(
    "/alarms/{id}/ack",
    response_model=Acknowledgement,
    summary="Alarm quittieren (UI-/Audit-Aktion, kein Aktor)",
    tags=["Alarms"],
    responses={
        400: {"model": Error, "description": "Ungueltige Alarm-ID (`id < 1`)."},
        404: {"model": Error, "description": "Alarm mit dieser ID existiert nicht."},
        409: {"model": Error, "description": "Alarm bereits quittiert/geschlossen (NF-09)."},
        422: {"model": Error, "description": "Ungueltiger Request-Body (Schema-Validierung)."},
        503: {"model": Error, "description": "G2 momentan nicht lieferfaehig (Persistenz)."},
    },
)
def acknowledge_alarm(
    id: int,
    body: AckRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
    response: Response,
) -> Acknowledgement | JSONResponse:
    """Quittiert einen Alarm (DTB-24, FA-10) — reine UI-/Audit-Aktion, kein Aktor (RB-01).

    Setzt den Alarm-Zustand atomar `active -> acknowledged`, schreibt einen append-only
    `acknowledgement`-Eintrag (NF-09) und einen `alarm_acknowledged`-Audit-Eintrag in EINER
    Transaktion (AcknowledgementRepository). Fehlerbilder strikt nach `openapi.yaml`:

    - `id < 1` -> **400** (`BAD_REQUEST`): bewusst hier geprueft (Pfad-Param ohne ge-Constraint),
      damit id=0 als Geschaeftsregel-400 landet statt als 422 im Validierungs-Handler.
    - Body ungueltig (z. B. `operator` fehlt) -> **422** (globaler RequestValidationError-Handler).
    - Alarm nicht vorhanden -> **404**; bereits acknowledged/cleared -> **409** (Double-Ack, NF-09).
    - Persistenz-/DB-Ausfall -> **503** (`Error {code, message}`, nie GRUEN/Leak; NF-01/Contract D).

    Auth: im Prototyp (M2/Contract) bewusst KEIN Auth-Header; additiv in M3 ohne Breaking Change
    ergaenzbar (`Authorization`, vgl. DTB-63). Erfolg -> **200** + `Acknowledgement`.
    `Cache-Control: no-store` auch hier (Konvention der /v1-Naht, NF-01-Geist).
    """
    response.headers.update(NO_STORE_HEADERS)
    if id < 1:
        return error_response(400, BAD_REQUEST_CODE, "Ungueltige Alarm-ID.")
    try:
        return runtime.ack_repo.acknowledge(id, body.operator, body.note, datetime.now(UTC))
    except AlarmNotFoundError:
        return error_response(404, NOT_FOUND_CODE, f"Alarm {id} nicht gefunden.")
    except AlarmNotAcknowledgeableError as exc:
        return error_response(
            409,
            ALARM_ALREADY_ACKNOWLEDGED_CODE,
            f"Alarm {id} ist bereits im Zustand '{exc.state.value}'.",
        )
    except RepositoryError as exc:
        # DB-Ausfall: Detail server-seitig loggen, nach aussen nur generisch (Contract D).
        logger.error("ack: Persistenz nicht verfuegbar (alarm_id=%s): %s", id, exc)
        return service_unavailable("G2 momentan nicht lieferfaehig.")
