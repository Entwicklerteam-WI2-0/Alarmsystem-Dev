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
import json
import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers
from starlette.responses import StreamingResponse

from src.api.broadcaster import AlarmBroadcaster
from src.api.exceptions import RuntimeNotReadyError
from src.api.v1 import _MAX_LOGGED_HEADER_LEN, _sanitize_header_value, stream_alarms
from src.main import app, get_runtime
from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm
from tests.sse_helpers import disconnect_after, never_disconnected

client = TestClient(app)

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset_overrides_and_state():
    # Selbst-isolierend statt auf die Cleanup-Disziplin der Geschwister-Module zu vertrauen:
    # das Modul beruehrt den geteilten globalen app-Singleton, also raeumt es nach JEDEM Test
    # eigene Dependency-Overrides + State ab (Projektmuster, vgl. test_e2e_ingest_assessment_api).
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "runtime"):
            del app.state.runtime


def _alarm(alarm_id: int) -> Alarm:
    return Alarm(
        id=alarm_id,
        assessment_id=alarm_id * 10,
        severity=AlarmSeverity.WARNING,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )


def test_stream_response_is_event_stream_with_no_store():
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(is_disconnected=never_disconnected, headers=Headers({}))

        response = await stream_alarms(runtime=runtime, request=request)

        assert isinstance(response, StreamingResponse)
        # Erfolgs-Status der G2->G3-Naht pinnen: der Contract (openapi.yaml) verlangt 200 fuer
        # den SSE-Stream; G3s EventSource wertet JEDEN Nicht-200 als Verbindungsfehler. Ein
        # Refactor, der dem Erfolgs-Stream einen abweichenden Code gaebe (z. B. 204), liefe sonst
        # gruen durch.
        assert response.status_code == 200
        # Contract: SSE.
        assert response.media_type == "text/event-stream"
        # Echtzeit-Sicherheitsnaht: kein Proxy/Browser darf den Stream cachen (NF-01-Geist).
        assert response.headers["cache-control"] == "no-store"
        # Reverse-Proxy-Buffering aus -> Events erreichen G3 sofort statt blockweise.
        assert response.headers["x-accel-buffering"] == "no"
        # KEIN Connection-Header: in HTTP/2 verboten (RFC 9113 §8.2.2), in HTTP/1.1 redundant.
        # Absenz pinnen -> ein versehentliches Wieder-Hinzufuegen faellt im Test auf.
        assert "connection" not in response.headers
        # Body-Generator (nicht gestartet) sauber schliessen -> keine "never awaited"-Warnung.
        await response.body_iterator.aclose()

    asyncio.run(scenario())


def test_stream_emits_published_alarm_as_frame():
    # End-to-end durch den Endpoint-Body: ein am Broadcaster publizierter Alarm erscheint als
    # SSE-Frame (id: + data:Alarm-JSON). Beweist die Endpoint-Verdrahtung (reserve -> _frames ->
    # sse_alarm_frames),
    # die der Header-Test (kein Body-Iterieren) nicht mitprueft.
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(is_disconnected=disconnect_after(1), headers=Headers({}))

        response = await stream_alarms(runtime=runtime, request=request)
        # reserve() in stream_alarms abonniert SYNCHRON -> das Abo (und die Queue) existiert
        # sofort, ohne dass der Generator schon iteriert wurde. Also direkt einreihen + treiben.
        assert broadcaster.subscriber_count == 1
        gen = response.body_iterator
        broadcaster.publish(_alarm(7))
        frame = await asyncio.wait_for(gen.__anext__(), timeout=1)

        assert frame.startswith("id: 7\n")
        # Wire-Form-Guard: vollstaendiges Alarm-Schema auf der `data:`-Naht pinnen (E-37),
        # statt nur 2 von 5 Feldern per Substring zu pruefen — faengt extra/fehlende Felder.
        data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
        payload = json.loads(data_line[len("data: ") :])
        assert set(payload) == {"id", "assessment_id", "severity", "raised_at", "state"}
        assert payload["id"] == 7
        assert payload["assessment_id"] == 70  # alarm_id * 10
        assert payload["severity"] == "warning"
        assert payload["state"] == "active"
        assert datetime.fromisoformat(payload["raised_at"].replace("Z", "+00:00")) == _T0
        await gen.aclose()  # Abo abbauen (_frames()-finally -> broadcaster.release)
        assert broadcaster.subscriber_count == 0

    asyncio.run(scenario())


def test_stream_emits_two_published_alarms_in_id_order():
    # End-to-end durch den Endpoint-Body: ZWEI nacheinander publizierte Alarme erscheinen als
    # ZWEI SSE-Frames in id:-Reihenfolge. Pinnt den Re-Yield-Loop in v1._frames (Z.130-133:
    # `async for frame in sse_alarm_frames(...): yield frame`) — eine Regression, die ihn nach
    # dem ersten Frame verlaesst (yield frame; return/break), liefere G3 im Dauerbetrieb
    # (Daseinszweck DTB-61: Live-Push) nur das erste Alarm-Event und danach Stille. Die
    # Mehrfach-Sequenz war bisher nur direkt gegen sse_alarm_frames getestet, was den
    # Re-Yield-Loop im Endpoint-Body komplett umgeht.
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        # disconnect_after(2) -> der Generator liefert genau zwei Frames, dann beendet er sauber.
        request = SimpleNamespace(is_disconnected=disconnect_after(2), headers=Headers({}))

        response = await stream_alarms(runtime=runtime, request=request)
        gen = response.body_iterator  # reserve() hat synchron abonniert -> Queue existiert

        broadcaster.publish(_alarm(1))
        frame1 = await asyncio.wait_for(gen.__anext__(), timeout=1)
        assert frame1.startswith("id: 1\n")

        # Zweiter Alarm durch denselben offenen Stream -> der Re-Yield-Loop MUSS einen ZWEITEN
        # Frame liefern (nicht nach dem ersten enden). Genau das umgeht der Direkttest gegen
        # sse_alarm_frames; hier laeuft es durch den echten Endpoint-Body v1._frames.
        broadcaster.publish(_alarm(2))
        frame2 = await asyncio.wait_for(gen.__anext__(), timeout=1)
        assert frame2.startswith("id: 2\n")

        await gen.aclose()  # Abo abbauen (_frames()-finally -> broadcaster.release)
        assert broadcaster.subscriber_count == 0

    asyncio.run(scenario())


def test_endpoint_calls_sse_alarm_frames_with_default_heartbeat(monkeypatch):
    # Call-Site-Guard (DTB-61): der Endpoint MUSS sse_alarm_frames OHNE expliziten heartbeat_s
    # aufrufen und sich auf den _HEARTBEAT_S-Default (~15 s Contract) verlassen. Eine Entkopplung
    # am Call-Site (z. B. heartbeat_s=300) liefe G2 mit falschem Heartbeat auf der eingefrorenen
    # G2->G3-Naht, waehrend der Konstanten-/Signatur-Pin in test_alarm_broadcaster gruen bliebe —
    # dieser Test exerziert die REALE Aufruf-Stelle (v1.py Z. 132) statt nur die Signatur.
    captured: dict[str, object] = {}

    async def _spy(_queue, _is_disconnected, *args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        for _ in ():  # leerer AsyncGenerator-Body (kein Frame), macht _spy zum Generator
            yield

    monkeypatch.setattr("src.api.v1.sse_alarm_frames", _spy)

    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(is_disconnected=never_disconnected, headers=Headers({}))

        response = await stream_alarms(runtime=runtime, request=request)
        # Body iterieren -> der _frames-Generator ruft sse_alarm_frames mit den realen Call-Args.
        async for _ in response.body_iterator:
            pass

    asyncio.run(scenario())
    # Kein positionaler 3. Arg und kein heartbeat_s-kwarg -> Endpoint verlaesst sich auf Default.
    assert captured["args"] == ()
    assert "heartbeat_s" not in captured["kwargs"]


def test_stream_logs_last_event_id_on_reconnect(caplog):
    # Reconnect-Mechanismus (Contract): der Client schickt beim Wiederverbinden den zuletzt
    # gesehenen `id:`-Wert als Last-Event-ID-Header. G2 puffert KEINE Historie (Resync =
    # GET /v1/alarms, DTB-31) -> der Header wird nur protokolliert (Diagnose), nicht repliziert.
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        # Echte Starlette-Headers (case-INsensitiv) statt plain dict: SSE-Clients senden den
        # kanonischen Header 'Last-Event-ID'; der Fake muss diese Realitaet modellieren, sonst
        # koppelt der Test an die exakte Zugriffs-Schreibweise im Produktionscode.
        request = SimpleNamespace(
            is_disconnected=never_disconnected, headers=Headers({"Last-Event-ID": "7"})
        )
        with caplog.at_level(logging.INFO, logger="src.api.v1"):
            response = await stream_alarms(runtime=runtime, request=request)
            await response.body_iterator.aclose()
        # Die konkrete Reconnect-Diagnosezeile pinnen, nicht nur das Zeichen '7': der
        # geloggte Wert MUSS der eingehende Last-Event-ID-Header sein, und die Semantik
        # (kein Replay, Resync via GET /v1/alarms, DTB-31) muss erkennbar bleiben.
        msgs = [record.getMessage() for record in caplog.records]
        assert any("Last-Event-ID=7" in m for m in msgs)
        assert any("DTB-31" in m for m in msgs)

    asyncio.run(scenario())


def test_stream_does_not_log_reconnect_on_first_connection(caplog):
    # Negativfall zum Reconnect-Log (v1.py Z. 122 `if last_event_id:`): eine ERSTverbindung OHNE
    # Last-Event-ID-Header darf KEINE Reconnect-/Resync-Zeile loggen. Eine Regression, die die
    # `if`-Schranke entfernt oder den Resync-Hinweis bedingungslos loggt, wuerde jede frische SSE-
    # Verbindung mit einem irrefuehrenden 'G3 sollte resyncen (Datenverlust)'-Signal fluten —
    # ohne diesen Test bliebe der False-Zweig ungeprueft.
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(is_disconnected=never_disconnected, headers=Headers({}))
        with caplog.at_level(logging.INFO, logger="src.api.v1"):
            response = await stream_alarms(runtime=runtime, request=request)
            await response.body_iterator.aclose()
        msgs = [record.getMessage() for record in caplog.records]
        assert not any("Last-Event-ID" in m for m in msgs)
        assert not any("DTB-31" in m for m in msgs)

    asyncio.run(scenario())


def test_stream_releases_slot_if_response_construction_fails(monkeypatch):
    # Theoretischer Slot-Leak (PR-Review): wirft die StreamingResponse-Konstruktion NACH
    # reserve() (akademisch, z. B. OOM), muss der reservierte Slot trotzdem freigegeben werden —
    # sonst belegt eine nie gestartete Verbindung dauerhaft Kapazitaet (der _frames-finally
    # liefe nie, weil der Generator nie startet).
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(is_disconnected=never_disconnected, headers=Headers({}))

        def _boom(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("response-Konstruktion kaputt")

        monkeypatch.setattr("src.api.v1.StreamingResponse", _boom)
        with pytest.raises(RuntimeError):
            await stream_alarms(runtime=runtime, request=request)

        assert broadcaster.subscriber_count == 0  # Slot freigegeben, kein Leak

    asyncio.run(scenario())


def test_stream_returns_503_when_at_capacity():
    # Connection-Cap (Ressourcenschutz): ist der Broadcaster voll (max gleichzeitige Abos),
    # weist der Endpoint die neue SSE-Verbindung mit 503 + Contract-Error ab, statt unbegrenzt
    # Speicher zu binden. Rein abweisend (RB-01), kein Aktor; kein StreamingResponse.
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster(max_subscribers=1)
        broadcaster.reserve()  # Kapazitaet voll belegt
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(is_disconnected=never_disconnected, headers=Headers({}))

        response = await stream_alarms(runtime=runtime, request=request)

        assert not isinstance(response, StreamingResponse)
        assert response.status_code == 503
        body = json.loads(response.body)
        assert set(body) == {"code", "message"}
        assert body["code"] == "SERVICE_UNAVAILABLE"

    asyncio.run(scenario())


def test_sanitize_header_value_strips_all_non_printable():
    # Defense-in-depth gegen Log-Forging/-Obfuskation: NICHT nur CR/LF, sondern ALLE
    # nicht-druckbaren Zeichen entfernen (Unicode-Zeilentrenner, Tabs, C0/C1-Controls,
    # Zero-Width). So kann ein client-kontrollierter Header keine Log-Zeile faelschen
    # oder verschleiern. Normaler Text + Leerzeichen bleiben erhalten.
    raw = (
        "7"
        + chr(13)  # CR
        + chr(10)  # LF
        + "A"
        + chr(0x2028)  # Line Separator
        + "B"
        + chr(0x2029)  # Paragraph Separator
        + "C"
        + chr(9)  # Tab
        + "D"
        + chr(0)  # NUL
        + "E"
        + chr(27)  # ESC
        + "F ok"
    )
    assert _sanitize_header_value(raw) == "7ABCDEF ok"


def test_sanitize_header_value_truncates():
    assert _sanitize_header_value("x" * 200) == "x" * _MAX_LOGGED_HEADER_LEN


def test_stream_sanitizes_last_event_id_in_log(caplog):
    # Log-Injection-Schutz (NF-09 Log-Integritaet): der client-kontrollierte Last-Event-ID-
    # Header darf keine gefaelschten Log-Zeilen erzeugen. CR/LF werden entfernt + der Wert
    # begrenzt -> die Diagnose bleibt, aber ohne eingeschmuggelte Zeile.
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(
            is_disconnected=never_disconnected,
            headers=Headers({"last-event-id": "7\r\nINFO:root:GEFAELSCHT"}),
        )
        with caplog.at_level(logging.INFO, logger="src.api.v1"):
            response = await stream_alarms(runtime=runtime, request=request)
            await response.body_iterator.aclose()
        messages = [record.getMessage() for record in caplog.records]
        joined = "\n".join(messages)
        # Sanitisierter Wert (ohne CR/LF) ist geloggt ...
        assert any("7INFO:root:GEFAELSCHT" in m for m in messages)
        # ... aber KEIN eingeschmuggelter Zeilenumbruch im ID-Wert.
        assert "7\r\n" not in joined
        assert "7\nINFO" not in joined

    asyncio.run(scenario())


def test_stream_warns_when_last_event_id_was_sanitized(caplog):
    # Security-Observability (PR-Review): enthielt der client-kontrollierte Last-Event-ID-Header
    # nicht-druckbare Zeichen (moegl. Injection-/Log-Forging-Versuch), MUSS das als WARNING
    # sichtbar sein — nicht nur stillschweigend bereinigt. Sonst sieht ein Ops-/Security-Team
    # einen Angriffsversuch nicht.
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(
            is_disconnected=never_disconnected,
            headers=Headers({"last-event-id": "7\r\nINJECT"}),
        )
        with caplog.at_level(logging.WARNING, logger="src.api.v1"):
            response = await stream_alarms(runtime=runtime, request=request)
            await response.body_iterator.aclose()
        assert any(
            record.levelno == logging.WARNING and "Injection" in record.getMessage()
            for record in caplog.records
        )

    asyncio.run(scenario())


def test_stream_does_not_warn_on_clean_last_event_id(caplog):
    # Negativ: ein sauberer (druckbarer) Last-Event-ID erzeugt KEINE Injection-Warnung
    # (sonst Alarm-Muedigkeit -> echte Angriffsversuche gehen unter).
    async def scenario() -> None:
        broadcaster = AlarmBroadcaster()
        runtime = SimpleNamespace(alarm_broadcaster=broadcaster)
        request = SimpleNamespace(
            is_disconnected=never_disconnected, headers=Headers({"last-event-id": "42"})
        )
        with caplog.at_level(logging.WARNING, logger="src.api.v1"):
            response = await stream_alarms(runtime=runtime, request=request)
            await response.body_iterator.aclose()
        assert not any(
            record.levelno == logging.WARNING and "Injection" in record.getMessage()
            for record in caplog.records
        )

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
        # Nur den selbst gesetzten Override entfernen (nicht den GESAMTEN Dict leeren) -> keine
        # Cross-Test-Effekte ueber die globale app, falls andere Module/Fixtures Overrides halten.
        app.dependency_overrides.pop(get_runtime, None)
