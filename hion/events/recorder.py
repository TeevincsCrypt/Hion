"""The single write path for mission events.

Every state transition in the engine goes through a :class:`MissionRecorder` so
that the persisted event log and the live stream can never drift apart.
"""

from __future__ import annotations

import logging
from typing import Any

from hion.domain.enums import AgentName, EventType
from hion.domain.models import Mission, MissionEvent
from hion.events.bus import EventBus

logger = logging.getLogger(__name__)


class MissionRecorder:
    """Appends events to a mission and broadcasts them."""

    def __init__(self, mission: Mission, bus: EventBus) -> None:
        self._mission = mission
        self._bus = bus

    @property
    def mission(self) -> Mission:
        return self._mission

    def emit(
        self,
        event_type: EventType,
        *,
        message: str = "",
        task_id: str | None = None,
        agent: AgentName | None = None,
        **data: Any,
    ) -> MissionEvent:
        """Record an event and push it to live subscribers."""
        event = MissionEvent(
            mission_id=self._mission.id,
            sequence=len(self._mission.events) + 1,
            type=event_type,
            task_id=task_id,
            agent=agent,
            message=message,
            data=data,
        )
        self._mission.events.append(event)
        self._mission.touch()
        logger.debug("[%s] %s %s", self._mission.id, event.type.value, event.message)
        self._bus.publish(event)
        return event
