"""Enumerations that define the Hion mission state machine."""

from __future__ import annotations

from enum import StrEnum


class MissionStatus(StrEnum):
    """Lifecycle of a mission."""

    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskStatus(StrEnum):
    """Lifecycle of a single task inside a mission."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    REVIEWING = "REVIEWING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentName(StrEnum):
    """The agents that make up the Hion crew."""

    COMMANDER = "commander"
    RESEARCH = "research"
    CREATOR = "creator"
    ANALYST = "analyst"
    CRITIC = "critic"
    GUARDIAN = "guardian"

    @classmethod
    def specialists(cls) -> tuple[AgentName, ...]:
        """Agents the Commander is allowed to delegate mission tasks to."""
        return (cls.RESEARCH, cls.CREATOR, cls.ANALYST)


class RiskLevel(StrEnum):
    """How dangerous an action is, and therefore how much oversight it needs."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def rank(self) -> int:
        return _RISK_RANK[self]

    def __ge__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank >= other.rank

    def __gt__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank > other.rank

    def __le__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank <= other.rank

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank < other.rank

    @classmethod
    def max(cls, *levels: RiskLevel) -> RiskLevel:
        return max(levels, key=lambda level: level.rank)


_RISK_RANK: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}


class EventType(StrEnum):
    """Every meaningful thing that can happen during a mission.

    The values are the wire format consumed by the Mission Control activity stream.
    """

    MISSION_CREATED = "mission.created"
    MISSION_PLANNED = "mission.planned"
    MISSION_COMPLETED = "mission.completed"
    MISSION_FAILED = "mission.failed"

    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_RETRYING = "task.retrying"

    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"

    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_BLOCKED = "tool.blocked"

    CRITIC_STARTED = "critic.started"
    CRITIC_COMPLETED = "critic.completed"
    REVISION_REQUESTED = "revision.requested"
    REVISION_EXHAUSTED = "revision.exhausted"

    GUARDIAN_REVIEW = "guardian.review"
    APPROVAL_REQUIRED = "approval.required"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_TIMED_OUT = "approval.timed_out"

    STREAM_HEARTBEAT = "stream.heartbeat"
