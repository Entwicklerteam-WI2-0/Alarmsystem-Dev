"""v1-API-Router des G2-Backends (Serving zu G3).

Sammelt die versionierten `/v1/`-Endpoints (AE-03). Aktuell: `GET /v1/thresholds`
(DTB-62) — liefert die aktuell konfigurierten Schwellenwerte fuer das G3-Menue.
Alle Endpoints hier sind **rein lesend** (RB-01-neutral): kein Aktor, keine
Runway-Steuerung.
"""

import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from src.api.broadcaster import StreamCapacityError, sse_alarm_frames
from src.api.responses import NO_STORE_HEADERS, service_unavailable
from src.api.runtime import Runtime, get_runtime
from src.config.loader import Thresholds
from src.model.schemas import Error

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
# ueberholten Stream-Zustands), keep-alive (Verbindung offen halten) und
# X-Accel-Buffering:no (schaltet das Response-Buffering eines Reverse-Proxys wie nginx
# fuer SSE ab -> Events erreichen G3 sofort statt blockweise).
_SSE_HEADERS = {
    "Cache-Control": "no-store",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

# Obergrenze fuer den geloggten Last-Event-ID-Wert (Diagnose reicht; verhindert ueberlange
# client-kontrollierte Log-Zeilen).
_MAX_LOGGED_HEADER_LEN = 64


def _sanitize_header_value(value: str) -> str:
    """Entfernt ALLE nicht-druckbaren Zeichen und begrenzt die Laenge eines Headerwerts.

    Schutz gegen Log-Injection/-Forging (NF-09 Log-Integritaet): ein eingeschmuggelter
    Zeilenumbruch ODER Unicode-Zeilentrenner (U+2028/U+2029) im (von G3 gesendeten)
    Last-Event-ID-Header koennte sonst eine gefaelschte/verschleierte Log-Zeile erzeugen.
    Gefiltert wird per str.isprintable() (entfernt CR/LF, Tabs, C0/C1-Controls,
    Zero-Width); normaler Text + Leerzeichen bleiben. Geloggt wird nur der bereinigte,
    begrenzte Wert.
    """
    return "".join(ch for ch in value if ch.isprintable())[:_MAX_LOGGED_HEADER_LEN]


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
        logger.info(
            "SSE-Reconnect mit Last-Event-ID=%s — G3 sollte via GET /v1/alarms resyncen "
            "(DTB-31); G2 liefert keine Historie nach.",
            _sanitize_header_value(last_event_id),
        )

    broadcaster = runtime.alarm_broadcaster
    try:
        # Abo SYNCHRON reservieren (race-frei) -> bei voller Kapazitaet kann der Endpoint
        # noch contract-konform mit 503 antworten, BEVOR ein StreamingResponse (200) beginnt.
        queue = broadcaster.reserve()
    except StreamCapacityError as exc:
        logger.warning("SSE-Stream-Kapazitaet erreicht — Verbindung mit 503 abgewiesen: %s", exc)
        return service_unavailable("Stream-Kapazitaet erreicht; bitte spaeter erneut verbinden.")

    async def _frames() -> AsyncIterator[str]:
        try:
            async for frame in sse_alarm_frames(queue, request.is_disconnected):
                yield frame
        finally:
            # Abo am Verbindungsende abmelden (Kapazitaet freigeben, Leak verhindern).
            broadcaster.release(queue)

    return StreamingResponse(_frames(), media_type="text/event-stream", headers=_SSE_HEADERS)
