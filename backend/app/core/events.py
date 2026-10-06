"""In-process async event bus powering SSE and internal consumers.

Subscribers receive JSON-serializable event dicts with the envelope:
    {"seq": int, "type": str, "ts": float, "data": {...}}
"""
from __future__ import annotations

import asyncio
import itertools
import time
from collections import deque
from typing import Any

from app.core.logging import get_logger

log = get_logger("events")


class EventBus:
    """Fan-out pub/sub. Safe to publish from the event-loop thread."""

    def __init__(self, history_size: int = 300, queue_size: int = 2000) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._seq = itertools.count(1)
        self._queue_size = queue_size
        self.published_total = 0

    def subscribe(self, replay_history: bool = True) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        if replay_history:
            for event in self._history:
                q.put_nowait(event)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    def publish(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        event: dict[str, Any] = {
            "seq": next(self._seq),
            "type": event_type,
            "ts": time.time(),
            "data": data,
        }
        self._history.append(event)
        self.published_total += 1
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer: drop oldest to make room instead of blocking the bus.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
        return event

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self._history)[-limit:]


# Shared process-wide bus
bus = EventBus()
