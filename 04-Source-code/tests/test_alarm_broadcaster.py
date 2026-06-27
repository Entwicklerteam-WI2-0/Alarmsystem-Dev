"""Tests fuer den In-Process-Alarm-Broadcaster + SSE-Frame-Generator (DTB-61).

`AlarmBroadcaster` ist das Pub/Sub hinter `GET /v1/alarms/stream` (E-37): der
Bewertungszyklus (run_scheduler, auf dem Event-Loop) ruft `publish(alarm)`; jeder
offene SSE-Client haelt ein `subscribe()`-Abo (asyncio.Queue) und konsumiert daraus.

Belegt:
- Fan-out an mehrere Abonnenten; Abbau des Abos beim Verbindungsende.
- Bounded Queue + Drop-oldest bei Ueberlauf (langsamer Client; Resync via DTB-31 deckt ab).
- `publish` ist best-effort (NF-01): nie werfend, auch ohne Abonnenten.
- `sse_alarm_frames` formatiert den Contract-Frame (`id:`/`data:` = Alarm-JSON) und
  sendet bei Leerlauf den Heartbeat-Kommentar (`:keep-alive`).

Bewusst ohne pytest-asyncio: jedes Szenario laeuft via `asyncio.run` (gleicher Loop wie
im Betrieb -> kein cross-thread Queue-Zugriff).
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

from src.api.broadcaster import AlarmBroadcaster, sse_alarm_frames
from src.model.enums import AlarmSeverity, AlarmState
from src.model.schemas import Alarm

_T0 = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


def _alarm(alarm_id: int, severity: AlarmSeverity = AlarmSeverity.WARNING) -> Alarm:
    return Alarm(
        id=alarm_id,
        assessment_id=alarm_id * 10,
        severity=severity,
        raised_at=_T0,
        state=AlarmState.ACTIVE,
    )


def _disconnect_after(n: int) -> Callable[[], Awaitable[bool]]:
    """Liefert ein is_disconnected, das die ersten n Aufrufe False, dann True liefert."""
    calls = {"i": 0}

    async def _is_disconnected() -> bool:
        i = calls["i"]
        calls["i"] += 1
        return i >= n

    return _is_disconnected


async def _drain(gen: AsyncIterator[str]) -> list[str]:
    return [frame async for frame in gen]


# ---------------------------------------------------------------------------
# AlarmBroadcaster — Pub/Sub
# ---------------------------------------------------------------------------


def test_publish_delivers_alarm_to_subscriber():
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        async with bc.subscribe() as queue:
            bc.publish(_alarm(1))
            got = await asyncio.wait_for(queue.get(), timeout=1)
        assert got.id == 1
        assert got.severity is AlarmSeverity.WARNING

    asyncio.run(scenario())


def test_publish_fans_out_to_all_subscribers():
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        async with bc.subscribe() as q1, bc.subscribe() as q2:
            assert bc.subscriber_count == 2
            bc.publish(_alarm(5))
            a1 = await asyncio.wait_for(q1.get(), timeout=1)
            a2 = await asyncio.wait_for(q2.get(), timeout=1)
        assert a1.id == 5 and a2.id == 5

    asyncio.run(scenario())


def test_subscribe_cleans_up_on_exit():
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        assert bc.subscriber_count == 0
        async with bc.subscribe():
            assert bc.subscriber_count == 1
        # Verbindungsende -> Abo abgebaut (kein Leak langlebiger Queues).
        assert bc.subscriber_count == 0

    asyncio.run(scenario())


def test_publish_without_subscribers_is_noop():
    async def scenario() -> None:
        bc = AlarmBroadcaster()
        # Darf nicht werfen (best-effort, NF-01): ein Alarm ohne Zuhoerer geht verloren
        # (Resync via DTB-31 deckt ab), bricht aber nie den Bewertungszyklus.
        bc.publish(_alarm(1))
        assert bc.subscriber_count == 0

    asyncio.run(scenario())


def test_publish_swallows_subscriber_error():
    # Best-effort (NF-01): wirft ein einzelner Abonnent beim Zustellen, darf publish NICHT
    # werfen (sonst wuerde ein kaputter Stream-Client den Bewertungszyklus reissen). Ein
    # Stub-Abo, dessen full() wirft, simuliert den Fehlerfall am direktesten.
    class _BrokenQueue:
        def full(self) -> bool:
            raise RuntimeError("boom")

    bc = AlarmBroadcaster()
    bc._subscribers.add(_BrokenQueue())  # type: ignore[arg-type]  # noqa: SLF001

    bc.publish(_alarm(1))  # darf nicht werfen


def test_publish_drops_oldest_when_queue_full():
    async def scenario() -> None:
        bc = AlarmBroadcaster(max_queue=2)
        async with bc.subscribe() as queue:
            # 3 Alarme ohne Konsum -> Puffer (2) laeuft ueber -> aeltester (id=1) faellt raus.
            bc.publish(_alarm(1))
            bc.publish(_alarm(2))
            bc.publish(_alarm(3))
            first = await asyncio.wait_for(queue.get(), timeout=1)
            second = await asyncio.wait_for(queue.get(), timeout=1)
        # Der NEUESTE Alarm ueberlebt (relevanteste Lage); der aelteste wird verworfen.
        assert [first.id, second.id] == [2, 3]

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# sse_alarm_frames — Contract-Frame-Formatierung
# ---------------------------------------------------------------------------


def test_sse_frame_carries_alarm_as_json_with_event_id():
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()
        queue.put_nowait(_alarm(42, AlarmSeverity.CRITICAL))
        gen = sse_alarm_frames(queue, _disconnect_after(1), heartbeat_s=5)
        return await _drain(gen)

    frames = asyncio.run(scenario())
    assert len(frames) == 1
    frame = frames[0]
    # `id:` = Alarm-ID (Reconnect via Last-Event-ID), `data:` = Alarm-JSON, Leerzeile = Event-Ende.
    assert frame.startswith("id: 42\n")
    assert "data: " in frame
    assert frame.endswith("\n\n")
    assert '"id":42' in frame
    assert '"severity":"critical"' in frame
    assert '"state":"active"' in frame


def test_sse_emits_heartbeat_on_idle():
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()  # leer -> Timeout -> Heartbeat
        gen = sse_alarm_frames(queue, _disconnect_after(1), heartbeat_s=0.01)
        return await _drain(gen)

    frames = asyncio.run(scenario())
    # SSE-Kommentarzeile, damit G3 einen still gestorbenen Stream von einem ruhigen unterscheidet.
    assert frames == [":keep-alive\n\n"]


def test_sse_stops_immediately_when_already_disconnected():
    async def scenario() -> list[str]:
        queue: asyncio.Queue[Alarm] = asyncio.Queue()
        queue.put_nowait(_alarm(1))
        gen = sse_alarm_frames(queue, _disconnect_after(0), heartbeat_s=5)  # sofort getrennt
        return await _drain(gen)

    frames = asyncio.run(scenario())
    assert frames == []  # getrennter Client -> kein Frame, sauberer Abbruch
