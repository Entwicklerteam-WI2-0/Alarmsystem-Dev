"""Tests fuer GET /v1/alarms/stream (DTB-61, SSE-Alarm-Push an G3, E-37).

Belegt die HTTP-Naht: korrekter SSE-Media-Type + no-store/Proxy-Header, und der
Fail-safe-503, falls die Runtime (noch) nicht bereit ist. Die Frame-/Push-Semantik
(Alarm-JSON, Heartbeat, Fan-out, Drop) ist in test_alarm_broadcaster.py unit-getestet —
hier geht es nur um die Endpoint-Verdrahtung (RB-01: rein lesend/Push, kein Aktor).

Der 200-Pfad ruft die Endpoint-Coroutine DIREKT auf und prueft das StreamingResponse-
Objekt (Media-Type + Header), ohne den Body zu iterieren. Das ist bewusst kein
client.stream(...): ein endloser SSE-Stream ueber den TestClient blockiert beim
Schliessen (der Body-Generator parkt im Heartbeat-await) — der Direktaufruf ist
deterministisch und schnell. Der 503-Pfad geht ueber den TestClient, weil dort die
Dependency (get_runtime) VOR dem Streaming wirft -> normale JSON-Antwort.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from src.api.broadcaster import AlarmBroadcaster
from src.api.exceptions import RuntimeNotReadyError
from src.api.v1 import stream_alarms
from src.main import app, get_runtime
from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm

client = TestClient(app)


async def _never_disconnected() -> bool:
    return False


def _disconnect_after(n: int) -> Callable[[], Awaitable[bool]]:
    calls = {"i": 0}

    async def _is_disconnected() -> bool:
        i = calls["i"]
        calls["i"] += 1
        return i >= n

    return _is_disconnected


def _alarm(alarm_id: int) -> Alarm:
    return Alarm(
        id=alarm_id,
        assessment_id=alarm_id * 10,
        severity=AlarmSeverity.WARNING,
        raised_at=datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC),
        state=AlarmState.ACTIVE,
    )


def test_stream_response_is_event_stream_with_no_store():
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(is_disconnected=_never_disconnected)

        response = await stream_alarms(runtime=runtime, request=request)

        assert isinstance(response, StreamingResponse)
        # Contract: SSE.
        assert response.media_type == "text/event-stream"
        # Echtzeit-Sicherheitsnaht: kein Proxy/Browser darf den Stream cachen (NF-01-Geist).
        assert response.headers["cache-control"] == "no-store"
        # Reverse-Proxy-Buffering aus -> Events erreichen G3 sofort statt blockweise.
        assert response.headers["x-accel-buffering"] == "no"
        # Body-Generator (nicht gestartet) sauber schliessen -> keine "never awaited"-Warnung.
        await response.body_iterator.aclose()

    asyncio.run(scenario())


def test_stream_emits_published_alarm_as_frame():
    # End-to-end durch den Endpoint-Body: ein am Broadcaster publizierter Alarm erscheint als
    # SSE-Frame (id: + data:Alarm-JSON). Beweist die Verdrahtung subscribe() -> sse_alarm_frames,
    # die der Header-Test (kein Body-Iterieren) nicht mitprueft.
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(is_disconnected=_disconnect_after(1))

        response = await stream_alarms(runtime=runtime, request=request)
        gen = response.body_iterator
        # Den ersten Frame anfordern; der Generator subscribt + parkt auf der leeren Queue.
        first = asyncio.ensure_future(gen.__anext__())
        while broadcaster.subscriber_count == 0:
            await asyncio.sleep(0)  # warten, bis der Generator das Abo registriert hat

        broadcaster.publish(_alarm(7))
        frame = await asyncio.wait_for(first, timeout=1)

        assert frame.startswith("id: 7\n")
        assert '"id":7' in frame
        assert '"severity":"warning"' in frame
        await gen.aclose()  # Abo abbauen (subscribe()-finally)
        assert broadcaster.subscriber_count == 0

    asyncio.run(scenario())


def test_stream_runtime_not_ready_returns_503():
    # Runtime nicht bereit (lifespan unvollstaendig) -> get_runtime wirft -> Exception-Handler
    # liefert 503 mit dem Contract-Fehlerformat {code, message}, nie ein rohes 500/{detail}.
    def _raise() -> object:
        raise RuntimeNotReadyError("Runtime nicht initialisiert (Test).")

    app.dependency_overrides[get_runtime] = _raise
    try:
        response: httpx.Response = client.get("/v1/alarms/stream")
        assert response.status_code == 503
        body = response.json()
        assert set(body.keys()) == {"code", "message"}
        assert body["code"] == "SERVICE_UNAVAILABLE"
    finally:
        app.dependency_overrides.clear()
