"""The Commander: plans missions and synthesises their final result."""

from __future__ import annotations

import logging

from hion.agents.factory import AgentFactory
from hion.agents.runtime import extract_text, run_structured
from hion.domain.enums import AgentName, TaskStatus
from hion.domain.models import Mission, MissionPlan
from hion.errors import PlanningError
from hion.events.recorder import MissionRecorder
from hion.hooks.telemetry import MissionTelemetryHook

logger = logging.getLogger(__name__)

_PLAN_PROMPT = """\
Plan the mission for this goal.

GOAL
----
{goal}

Produce the objective, the success criteria, and the task graph. Assign each task
to research, creator or analyst, and wire dependencies with the task keys.
"""

_SYNTHESIS_PROMPT = """\
The mission is complete. Produce the final result the human will receive.

GOAL
----
{goal}

OBJECTIVE
---------
{objective}

SUCCESS CRITERIA
----------------
{criteria}

COMPLETED WORK
--------------
{work}

Write the final deliverable itself, in full. Lead with the answer to the goal.
Do not describe the process, do not narrate what the agents did, and do not add a
preamble. If any part of the goal could not be completed, state that plainly at the
end under a short "Limitations" heading, including anything that is still awaiting
human approval.
"""


class Commander:
    """Turns a goal into a plan, and finished tasks into a deliverable."""

    def __init__(self, factory: AgentFactory, recorder: MissionRecorder) -> None:
        self._factory = factory
        self._recorder = recorder

    async def plan(self, goal: str) -> MissionPlan:
        """Decompose a goal into a validated task graph.

        Raises:
            PlanningError: the model returned a plan Hion cannot execute.
        """
        hook = MissionTelemetryHook(self._recorder, AgentName.COMMANDER)
        agent = self._factory.build(AgentName.COMMANDER, hooks=[hook])
        plan = await run_structured(agent, _PLAN_PROMPT.format(goal=goal), MissionPlan)
        _validate_plan(plan)
        return plan

    async def synthesize(self, mission: Mission) -> str:
        """Compose the final mission result from completed task output."""
        hook = MissionTelemetryHook(self._recorder, AgentName.COMMANDER)
        agent = self._factory.build(AgentName.COMMANDER, hooks=[hook])
        result = await agent.invoke_async(
            _SYNTHESIS_PROMPT.format(
                goal=mission.goal,
                objective=mission.objective or mission.goal,
                criteria=_bullets(mission.success_criteria),
                work=_format_work(mission),
            )
        )
        return extract_text(result)


def _validate_plan(plan: MissionPlan) -> None:
    """Reject plans that are not executable before we act on them."""
    if not plan.tasks:
        raise PlanningError("The Commander returned a plan with no tasks.")

    keys = [task.key for task in plan.tasks]
    duplicates = {key for key in keys if keys.count(key) > 1}
    if duplicates:
        raise PlanningError(f"Plan contains duplicate task keys: {sorted(duplicates)}")

    known = set(keys)
    for task in plan.tasks:
        unknown = [dep for dep in task.depends_on if dep not in known]
        if unknown:
            raise PlanningError(f"Task {task.key!r} depends on unknown task(s) {unknown}.")
        if task.key in task.depends_on:
            raise PlanningError(f"Task {task.key!r} depends on itself.")
        if task.assigned_agent not in AgentName.specialists():
            raise PlanningError(
                f"Task {task.key!r} was assigned to {task.assigned_agent.value!r}, "
                f"which is not a delegatable specialist."
            )

    _assert_acyclic(plan)


def _assert_acyclic(plan: MissionPlan) -> None:
    """Depth-first cycle check over the planned dependency graph."""
    graph = {task.key: list(task.depends_on) for task in plan.tasks}
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(key: str, trail: list[str]) -> None:
        if key in done:
            return
        if key in visiting:
            cycle = " -> ".join([*trail, key])
            raise PlanningError(f"Plan contains a dependency cycle: {cycle}")
        visiting.add(key)
        for dep in graph[key]:
            visit(dep, [*trail, key])
        visiting.discard(key)
        done.add(key)

    for key in graph:
        visit(key, [])


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (none stated)"


def _format_work(mission: Mission) -> str:
    sections: list[str] = []
    for task in mission.tasks:
        if task.status is not TaskStatus.COMPLETED or not task.result:
            continue
        header = f"### {task.title} ({task.assigned_agent.value})"
        if task.critique:
            header += f"  [critic score: {task.critique.score}/100]"
        sections.append(f"{header}\n{task.result}")

    skipped = [t for t in mission.tasks if t.status is not TaskStatus.COMPLETED]
    if skipped:
        lines = "\n".join(
            f"- {t.title} ({t.assigned_agent.value}): {t.status.value}"
            + (f" - {t.error}" if t.error else "")
            for t in skipped
        )
        sections.append(f"### Tasks that did not complete\n{lines}")

    return "\n\n".join(sections) if sections else "(no completed task output)"
