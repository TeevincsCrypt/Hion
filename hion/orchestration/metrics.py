"""Mission metrics.

Computed from the mission's own state and event log when it reaches a terminal
state, so the numbers can never disagree with the activity stream a UI renders.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hion.domain.enums import EventType, TaskStatus
from hion.domain.models import Mission, MissionMetrics


def compute_metrics(
    mission: Mission,
    *,
    finished_at: datetime | None = None,
    pending_events: int = 0,
) -> MissionMetrics:
    """Summarise everything that happened during a mission.

    Args:
        mission: The mission to summarise.
        finished_at: When the mission ended. Defaults to now, which is what a
            live snapshot of a running mission wants.
        pending_events: Events the caller is about to emit but has not yet. The
            engine computes metrics so it can put them *inside* the terminal
            event, which would otherwise leave ``events_recorded`` one short of
            the log a UI ends up holding.
    """
    finished = finished_at or datetime.now(UTC)
    events = mission.events
    tasks = mission.tasks

    # A blocked call is counted only as blocked, so tool_calls means "actually ran".
    tool_events = [
        e for e in events if e.type is EventType.TOOL_COMPLETED and e.status != "blocked"
    ]
    critic_scores = [
        task.critique.score for task in tasks if task.critique is not None
    ]

    usage = _sum_usage(mission)

    return MissionMetrics(
        total_tasks=len(tasks),
        completed_tasks=sum(1 for t in tasks if t.status is TaskStatus.COMPLETED),
        failed_tasks=sum(1 for t in tasks if t.status is TaskStatus.FAILED),
        tasks_accepted_with_open_critique=sum(
            1
            for e in events
            if e.type is EventType.TASK_COMPLETED and e.data.get("degraded") is True
        ),
        retries=sum(t.retry_count for t in tasks),
        agent_invocations=sum(1 for e in events if e.type is EventType.AGENT_STARTED),
        tool_calls=len(tool_events),
        tool_calls_blocked=sum(1 for e in events if e.type is EventType.TOOL_BLOCKED),
        approvals_requested=sum(1 for e in events if e.type is EventType.APPROVAL_REQUIRED),
        approvals_granted=sum(1 for e in events if e.type is EventType.APPROVAL_GRANTED),
        approvals_rejected=sum(1 for e in events if e.type is EventType.APPROVAL_REJECTED),
        approvals_timed_out=sum(1 for e in events if e.type is EventType.APPROVAL_TIMED_OUT),
        revisions_requested=sum(1 for e in events if e.type is EventType.REVISION_REQUESTED),
        events_recorded=len(events) + pending_events,
        duration_seconds=round((finished - mission.created_at).total_seconds(), 3),
        started_at=mission.created_at,
        finished_at=finished,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        total_tokens=usage["total_tokens"],
        average_critic_score=(
            round(sum(critic_scores) / len(critic_scores), 1) if critic_scores else None
        ),
    )


def _sum_usage(mission: Mission) -> dict[str, int]:
    """Token usage across every specialist run recorded on the mission."""
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for task in mission.tasks:
        for run in task.runs:
            for key in totals:
                totals[key] += int(run.usage.get(key, 0))
    return totals
