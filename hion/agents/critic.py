"""The Critic: structured evaluation of another agent's result."""

from __future__ import annotations

import logging

from hion.agents.factory import AgentFactory
from hion.agents.runtime import run_structured
from hion.config import Settings
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

RESULT UNDER REVIEW (attempt {attempt} of {max_attempts})
--------------------------------------------------------
{result}

Score every dimension, then decide. Check each acceptance criterion individually
and name any that is not met.
"""

#: Human-readable labels for the dimension names, used when the engine has to
#: synthesise a required change the Critic forgot to write.
_DIMENSION_LABELS = {
    "factual_support": "factual support: back every claim with evidence from the research",
    "completeness": "completeness: cover every part of the task and every acceptance criterion",
    "consistency": "consistency: remove contradictions with itself and with upstream results",
    "task_compliance": "task compliance: do the task as specified, in the form requested",
    "source_quality": "source quality: cite real, primary sources for load-bearing claims",
    "actionable_usefulness": "actionable usefulness: make it usable as-is by its audience",
}


class Critic:
    """Evaluates task results and decides whether they pass."""

    def __init__(self, factory: AgentFactory, recorder: MissionRecorder, settings: Settings) -> None:
        self._factory = factory
        self._recorder = recorder
        self._settings = settings

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
                result=result or "(the agent returned nothing)",
                attempt=task.retry_count + 1,
                max_attempts=self._settings.max_revisions + 1,
            ),
            Critique,
        )
        return self.normalise(critique)

    def normalise(self, critique: Critique) -> Critique:
        """Reconcile a critique against Hion's calibration rules.

        A critic that can be talked into approving is not a quality gate, so the
        verdict is not taken purely on the model's word:

        * a rejection must carry something actionable to fix;
        * an "approval" that still lists required changes is a rejection;
        * an approval below the overall threshold is a rejection;
        * an approval with any single failing dimension is a rejection, so a
          strong average cannot hide a broken axis.
        """
        updates: dict[str, object] = {}
        required = list(critique.required_changes)
        approved = critique.approved

        if approved and required:
            approved = False

        if approved and critique.score < self._settings.critic_approval_threshold:
            approved = False
            required.append(
                f"Raise overall quality: scored {critique.score}/100, "
                f"below the {self._settings.critic_approval_threshold} approval threshold."
            )

        if approved and critique.dimensions is not None:
            name, score = critique.dimensions.weakest()
            if score < self._settings.critic_min_dimension_score:
                approved = False
                required.append(f"Fix {_DIMENSION_LABELS.get(name, name)} (scored {score}/100).")

        if not approved and not required:
            required = list(critique.issues) or [
                "Address the issues raised in the critique reasoning."
            ]

        if approved != critique.approved:
            updates["approved"] = approved
        if required != critique.required_changes:
            updates["required_changes"] = required
        return critique.model_copy(update=updates) if updates else critique


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (none stated)"
