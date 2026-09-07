"""The single write path for mission events.

Every state transition in the engine goes through a :class:`MissionRecorder` so
that the persisted event log and the live stream can never drift apart.

What is recorded: actions and decisions - which agent ran, which tool it called,
what the Critic decided, what the Guardian classified, how long it took. What is
never recorded: model reasoning. Agent output is read from text content blocks
only, so reasoning blocks are dropped before they can reach an event.
"""

from __future__ import annotations

import logging
from typing import Any

from hion.domain.enums import AgentName, EventType, RiskLevel
from hion.domain.models import Mission, MissionEvent
from hion.events.bus import EventBus

logger = logging.getLogger(__name__)

#: Longest ``result_summary`` an event will carry. Enough to render a card,
#: short enough that the log is not a second copy of every deliverable.
SUMMARY_LIMIT = 500


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
        status: str | None = None,
        duration_ms: int | None = None,
        retry_count: int | None = None,
        tool_name: str | None = None,
        risk_level: RiskLevel | None = None,
        error: str | None = None,
        result_summary: str | None = None,
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
            status=status,
            duration_ms=duration_ms,
            retry_count=retry_count,
            tool_name=tool_name,
            risk_level=risk_level,
            error=error,
            result_summary=summarize(result_summary),
            data=data,
        )
        self._mission.events.append(event)
        self._mission.touch()
        logger.debug("[%s] %s %s", self._mission.id, event.type.value, event.message)
        self._bus.publish(event)
        return event


def summarize(text: str | None, limit: int = SUMMARY_LIMIT) -> str | None:
    """Condense agent output for the activity stream."""
    if not text:
        return None
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit].rstrip()}..."
