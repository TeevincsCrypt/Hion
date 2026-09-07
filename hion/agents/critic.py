"""The Critic: structured evaluation of another agent's result."""

from __future__ import annotations

import logging

from hion.agents.factory import AgentFactory
from hion.agents.runtime import run_structured
from hion.domain.enums import AgentName
from hion.domain.models import Critique, Task
from hion.events.recorder import MissionRecorder
from hion.hooks.telemetry import MissionTelemetryHook

logger = logging.getLogger(__name__)

_REVIEW_PROMPT = """\
Evaluate the result below. You are reviewing it, not rewriting it.

MISSION GOAL
------------
{goal}

TASK
----
Title: {title}
Assigned to: {agent}
Instruction: {description}

ACCEPTANCE CRITERIA
-------------------
{criteria}

UPSTREAM CONTEXT (results this task was built on)
------------------------------------------------
{context}

RESULT UNDER REVIEW (attempt {attempt})
---------------------------------------
{result}

Return your structured evaluation. Check every acceptance criterion individually.
"""


class Critic:
    """Evaluates task results and decides whether they pass."""

    def __init__(self, factory: AgentFactory, recorder: MissionRecorder) -> None:
        self._factory = factory
        self._recorder = recorder

    async def review(self, *, goal: str, task: Task, result: str, context: str) -> Critique:
        """Produce a structured critique of a task result."""
        hook = MissionTelemetryHook(self._recorder, AgentName.CRITIC, task_id=task.id)
        agent = self._factory.build(AgentName.CRITIC, hooks=[hook])
        critique = await run_structured(
            agent,
            _REVIEW_PROMPT.format(
                goal=goal,
                title=task.title,
                agent=task.assigned_agent.value,
                description=task.description,
                criteria=_bullets(task.acceptance_criteria),
                context=context or "(none)",
                result=result,
                attempt=task.retry_count + 1,
            ),
            Critique,
        )
        return _normalise(critique)


def _normalise(critique: Critique) -> Critique:
    """Guard against self-contradictory critiques.

    A rejection with nothing to fix is not actionable, and an approval carrying
    required changes is not an approval. Rather than trust the model to be
    internally consistent, reconcile it here.
    """
    if not critique.approved and not critique.required_changes:
        critique = critique.model_copy(
            update={
                "required_changes": critique.issues
                or ["Address the issues raised in the critique reasoning."]
            }
        )
    if critique.approved and critique.required_changes:
        critique = critique.model_copy(update={"approved": False})
    return critique


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (none stated)"
