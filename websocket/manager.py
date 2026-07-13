"""
websocket/manager.py — real-time request live-feed broadcaster (Week 5).

A single in-process ConnectionManager holds every open /ws/requests client.
After each routed request, router.py calls broadcast_request_event() with a
PII-safe summary; the manager fans it out to all connected browsers so the
Next.js live feed updates in real time.

Design:
  - Broadcast is best-effort and fire-and-forget: a slow or dead client must
    never break a response we already produced (mirrors tracking.db.log_request
    and gateway.cache.store). All send errors are swallowed; the dead socket is
    dropped from the active set.
  - Snapshot-then-send: the active set is copied under a lock, then sends happen
    outside the lock so one slow client can't block new connects/disconnects.
  - In-process only — correct for the current single-worker uvicorn deploy. If we
    ever run multiple workers, this needs Redis pub/sub behind it so an event
    produced by one worker reaches clients connected to another. Noted for later.
"""

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks open /ws/requests sockets and fans out events to all of them."""

    def __init__(self) -> None:
        self._active: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._active.add(websocket)
        logger.info(f"WS connect — {len(self._active)} client(s) on /ws/requests")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._active.discard(websocket)
        logger.info(f"WS disconnect — {len(self._active)} client(s) remain")

    async def broadcast(self, message: dict[str, Any]) -> None:
        # Snapshot under the lock, send outside it — a slow client must not block
        # connects/disconnects or other clients' sends.
        async with self._lock:
            targets = list(self._active)

        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)  # closed/broken socket — prune below

        if dead:
            async with self._lock:
                for ws in dead:
                    self._active.discard(ws)
            logger.debug(f"WS pruned {len(dead)} dead client(s)")

    @property
    def count(self) -> int:
        return len(self._active)


# Module-level singleton — imported by main.py (endpoint) and router.py (emit).
manager = ConnectionManager()


async def broadcast_request_event(event: dict[str, Any]) -> None:
    """
    Fire-and-forget wrapper used by the request path. Any failure — no clients,
    broken socket, serialization error — is swallowed here so it can never
    propagate into route()/_log_request and break a response already sent.
    """
    try:
        await manager.broadcast(event)
    except Exception as e:
        logger.warning(f"WS broadcast skipped — {type(e).__name__}: {e}")
