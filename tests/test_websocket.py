"""
tests/test_websocket.py — ConnectionManager fan-out + dead-socket pruning (Week 5).

The live feed must be best-effort: a broken client socket must never raise into
the request path, and must be dropped so it doesn't accumulate. We exercise the
manager with fake sockets (no real network) so the test is fast and hermetic.
"""

import pytest

pytest.importorskip("pytest_asyncio")

from websocket.manager import ConnectionManager, broadcast_request_event, manager


class FakeWS:
    """Minimal stand-in for a Starlette WebSocket."""

    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[dict] = []
        self.fail = fail
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self.fail:
            raise RuntimeError("dead socket")
        self.sent.append(message)


async def test_connect_accepts_and_tracks():
    m = ConnectionManager()
    ws = FakeWS()
    await m.connect(ws)
    assert ws.accepted is True
    assert m.count == 1


async def test_broadcast_fans_out_to_all_live_clients():
    m = ConnectionManager()
    a, b = FakeWS(), FakeWS()
    await m.connect(a)
    await m.connect(b)

    event = {"type": "request", "tier": "simple", "savings_usd": 0.001}
    await m.broadcast(event)

    assert a.sent == [event]
    assert b.sent == [event]


async def test_broadcast_prunes_dead_socket_and_still_delivers():
    m = ConnectionManager()
    good = FakeWS()
    bad = FakeWS(fail=True)
    await m.connect(good)
    await m.connect(bad)
    assert m.count == 2

    await m.broadcast({"hello": "world"})

    # Good client received; dead client was pruned, not raised.
    assert good.sent == [{"hello": "world"}]
    assert m.count == 1


async def test_disconnect_removes_client():
    m = ConnectionManager()
    ws = FakeWS()
    await m.connect(ws)
    await m.disconnect(ws)
    assert m.count == 0


async def test_broadcast_helper_never_raises_on_bad_client():
    """The fire-and-forget wrapper used by router._log_request must swallow
    everything — even if the underlying socket errors."""
    # Register a failing socket on the module singleton the helper broadcasts to.
    bad = FakeWS(fail=True)
    await manager.connect(bad)
    try:
        # Must return cleanly, never raise, regardless of the dead socket.
        result = await broadcast_request_event({"type": "request"})
        assert result is None
    finally:
        await manager.disconnect(bad)
