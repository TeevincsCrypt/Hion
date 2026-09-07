"""In-process publish/subscribe for mission events.

Publishing is deliberately synchronous and non-blocking so it can be called from
Strands hook callbacks (which run inside the agent event loop) without awaiting.
Subscribers get an unbounded queue; a slow SSE client can never stall a mission.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import AsyncIterator

from hion.domain.models import MissionEvent


class EventBus:
    """Fan-out of :class:`MissionEvent` to live subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[MissionEvent]]] = defaultdict(set)

    def publish(self, event: MissionEvent) -> None:
        """Deliver an event to every subscriber of its mission. Never blocks."""
        for queue in tuple(self._subscribers.get(event.mission_id, ())):
            queue.put_nowait(event)

    @contextlib.asynccontextmanager
    async def subscription(self, mission_id: str) -> AsyncIterator[asyncio.Queue[MissionEvent]]:
        """Subscribe to a mission's live event feed for the duration of the block."""
        queue: asyncio.Queue[MissionEvent] = asyncio.Queue()
        self._subscribers[mission_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[mission_id].discard(queue)
            if not self._subscribers[mission_id]:
                self._subscribers.pop(mission_id, None)

    def subscriber_count(self, mission_id: str) -> int:
        return len(self._subscribers.get(mission_id, ()))
