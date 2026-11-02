"""In-process event bus feeding the UI's Server-Sent Events stream.

`publish` is thread-safe: scans and the scheduler run in worker threads, while subscribers
live on the API server's event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any

Event = tuple[str, dict[str, Any]]


class EventBus:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[Event]] = set()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: str, data: dict[str, Any] | None = None) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._fanout, (event, data or {}))

    def _fanout(self, item: Event) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                continue  # slow client: drop rather than block everyone
            queue.put_nowait(item)
