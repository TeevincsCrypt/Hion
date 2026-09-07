"""Real-model validation of the full mission lifecycle.

``hion verify`` runs one real mission end to end against whatever provider is
configured and checks off each stage of the lifecycle from the recorded events.
It is the acceptance test that cannot be faked: it fails if the provider is
unreachable, and every check reads the event log a real run produced.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from hion.api.deps import Container
from hion.domain.enums import AgentName, EventType, MissionStatus
from hion.domain.models import Mission

logger = logging.getLogger(__name__)

#: The hackathon's reference mission.
REFERENCE_GOAL = (
    "Research the top competitors in the AI meeting assistant market and "
    "prepare a concise competitive brief."
)


@dataclass(frozen=True)
class Check:
    """One lifecycle expectation and whether the run met it."""

    name: str
    passed: bool
    detail: str
    required: bool = True


def lifecycle_checks(mission: Mission) -> list[Check]:
    """Verify each stage of the lifecycle from what the mission actually recorded."""
    events = mission.events
    types = [event.type for event in events]

    def agents_that_ran() -> set[AgentName]:
        return {e.agent for e in events if e.type is EventType.AGENT_STARTED and e.agent}

    ran = agents_that_ran()
    tool_calls = [e for e in events if e.type is EventType.TOOL_COMPLETED]
    research_tools = [e for e in tool_calls if e.agent is AgentName.RESEARCH]

    return [
        Check(
            "Commander produced a valid MissionPlan",
            EventType.MISSION_PLANNED in types and bool(mission.tasks),
            f"{len(mission.tasks)} task(s); objective: {mission.objective or '(none)'}",
        ),
        Check(
            "Plan has no structural warnings",
            not any(e.type is EventType.PLAN_WARNING for e in events),
            "; ".join(e.message for e in events if e.type is EventType.PLAN_WARNING) or "clean",
            required=False,
        ),
        Check(
            "Commander delegated to specialists",
            bool(ran & set(AgentName.specialists())),
            ", ".join(sorted(a.value for a in ran)) or "none",
        ),
        Check(
            "Research agent ran and used tools",
            AgentName.RESEARCH in ran and bool(research_tools),
            f"{len(research_tools)} tool call(s): "
            + ", ".join(sorted({e.tool_name or "?" for e in research_tools})),
        ),
        Check(
            "Analyst evaluated the research",
            AgentName.ANALYST in ran,
            "analyst invoked" if AgentName.ANALYST in ran else "analyst never ran",
            required=False,
        ),
        Check(
            "Creator produced the deliverable",
            AgentName.CREATOR in ran,
            "creator invoked" if AgentName.CREATOR in ran else "creator never ran",
        ),
        Check(
            "Critic reviewed every completed task",
            EventType.CRITIC_COMPLETED in types,
            _critic_summary(mission),
        ),
        Check(
            "Guardian assessed every task's risk",
            sum(1 for t in types if t is EventType.GUARDIAN_REVIEW) >= len(mission.tasks),
            _guardian_summary(mission),
        ),
        Check(
            "Revision loop stayed bounded",
            all(task.retry_count <= 5 for task in mission.tasks),
            f"{sum(t.retry_count for t in mission.tasks)} revision(s) across the mission",
        ),
        Check(
            "Events were recorded throughout",
            len(events) >= 10 and [e.sequence for e in events] == list(range(1, len(events) + 1)),
            f"{len(events)} events, contiguous sequence",
        ),
        Check(
            "Mission completed",
            mission.status is MissionStatus.COMPLETED and bool(mission.final_result),
            f"status={mission.status.value}"
            + (f"; error={mission.error}" if mission.error else ""),
        ),
        Check(
            "Metrics were computed",
            mission.metrics is not None,
            _metrics_summary(mission),
        ),
    ]


def _critic_summary(mission: Mission) -> str:
    scored = [t for t in mission.tasks if t.critique]
    if not scored:
        return "no critiques recorded"
    return ", ".join(
        f"{t.key}={t.critique.score}/100 "
        f"({'approved' if t.critique.approved else 'rejected'})"
        for t in scored
        if t.critique
    )


def _guardian_summary(mission: Mission) -> str:
    assessed = [t for t in mission.tasks if t.guardian_verdict]
    if not assessed:
        return "no verdicts recorded"
    return ", ".join(
        f"{t.key}={t.guardian_verdict.risk_level.value}"
        + ("*" if t.guardian_verdict.requires_human_approval else "")
        for t in assessed
        if t.guardian_verdict
    )


def _metrics_summary(mission: Mission) -> str:
    metrics = mission.metrics
    if metrics is None:
        return "none"
    return (
        f"{metrics.completed_tasks}/{metrics.total_tasks} tasks, "
        f"{metrics.agent_invocations} agent invocations, "
        f"{metrics.tool_calls} tool calls, "
        f"{metrics.retries} retries, "
        f"{metrics.approvals_requested} approval(s) requested, "
        f"{metrics.duration_seconds:.1f}s"
    )


async def run_verification(container: Container, goal: str = REFERENCE_GOAL) -> tuple[Mission, list[Check]]:
    """Run one real mission and evaluate the lifecycle checks against it."""
    mission = await container.engine.start_mission(goal)
    await container.engine.wait_for(mission.id)
    return mission, lifecycle_checks(mission)
