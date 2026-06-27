"""Geteilte SSE-Test-Helfer (DTB-61).

Vermeidet das Duplikat der `is_disconnected`-Stubs ueber die beiden SSE-Testmodule
(test_alarm_broadcaster.py, test_alarm_stream_endpoint.py) — PR-Review-Befund.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable

from src.api.broadcaster import AlarmBroadcaster
from src.model.schemas import Alarm


@contextlib.asynccontextmanager
async def subscribed(broadcaster: AlarmBroadcaster) -> AsyncIterator[asyncio.Queue[Alarm]]:
    """Test-Convenience: reserve() + garantiertes release() als Kontextmanager.

    BEWUSST hier (Test-Helper), NICHT in der Broadcaster-API: der Produktionspfad
    (`stream_alarms`, api/v1.py) ruft reserve()/release() DIREKT, damit reserve() VOR dem
    StreamingResponse laeuft (503 bei vollem Cap). Diese reserve+auto-release-Sugar lebt
    daher in den Tests -> die Grenze Produktions-API <-> Testhelfer ist statisch erzwungen
    (es gibt keine subscribe-artige Methode am Broadcaster, die man im Endpoint missbrauchen
    koennte).
    """
    queue = broadcaster.reserve()
    try:
        yield queue
    finally:
        broadcaster.release(queue)


async def never_disconnected() -> bool:
    """is_disconnected-Stub, der nie trennt (Client bleibt verbunden)."""
    return False


def disconnect_after(n: int) -> Callable[[], Awaitable[bool]]:
    """is_disconnected-Stub: die ersten n Aufrufe False, danach True."""
    i = 0

    async def _is_disconnected() -> bool:
        nonlocal i
        result = i >= n
        i += 1
        return result

    return _is_disconnected
