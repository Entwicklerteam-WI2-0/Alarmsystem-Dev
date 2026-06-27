"""Geteilte SSE-Test-Helfer (DTB-61).

Vermeidet das Duplikat der `is_disconnected`-Stubs ueber die beiden SSE-Testmodule
(test_alarm_broadcaster.py, test_alarm_stream_endpoint.py) — PR-Review-Befund.
"""

from collections.abc import Awaitable, Callable


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
