"""Execution of a single task by a specialist agent."""

from __future__ import annotations

import logging

from hion.agents.factory import AgentFactory
from hion.agents.runtime import AgentOutcome, extract_text, extract_usage
from hion.domain.enums import RiskLevel
from hion.domain.models import Critique, Task
from hion.events.recorder import MissionRecorder
from hion.hooks.guardian_gate import GuardianToolGate
from hion.hooks.telemetry import MissionTelemetryHook

logger = logging.getLogger(__name__)

_TASK_PROMPT = """\
MISSION GOAL
------------
{goal}

YOUR TASK
---------
{title}

{description}

ACCEPTANCE CRITERIA
-------------------
{criteria}

CONTEXT FROM COMPLETED TASKS
----------------------------
{context}

Do the work now and return the deliverable itself as your response.
"""

_REVISION_PROMPT = """\
MISSION GOAL
------------
{goal}

YOUR TASK
---------
{title}

{description}

ACCEPTANCE CRITERIA
-------------------
{criteria}

CONTEXT FROM COMPLETED TASKS
----------------------------
{context}

YOUR PREVIOUS ATTEMPT
---------------------
{previous}

THE CRITIC REJECTED IT (score {score}/100)
------------------------------------------
Issues found:
{issues}

Required changes:
{required_changes}

Critic's reasoning: {reasoning}

This is attempt {attempt} of {max_attempts}. Revise your work so every required
change is addressed. Return the full revised deliverable, not a diff and not a
description of what you changed. If a required change cannot be made because the
research does not support it, say so explicitly rather than inventing support.
"""


class SpecialistRunner:
    """Runs research / analyst / creator tasks through Strands."""

    def __init__(self, factory: AgentFactory, recorder: MissionRecorder, max_attempts: int) -> None:
        self._factory = factory
        self._recorder = recorder
        self._max_attempts = max_attempts

    async def run(
        self,
        *,
        goal: str,
        task: Task,
        context: str,
        approved_ceiling: RiskLevel,
        critique: Critique | None = None,
        previous_result: str | None = None,
    ) -> AgentOutcome:
        """Execute (or revise) a task with the assigned specialist agent."""
        telemetry = MissionTelemetryHook(self._recorder, task.assigned_agent, task_id=task.id)
        gate = GuardianToolGate(
            self._recorder,
            task.assigned_agent,
            approved_ceiling=approved_ceiling,
            task_id=task.id,
        )
        agent = self._factory.build(task.assigned_agent, hooks=[gate, telemetry])

        if critique and previous_result:
            prompt = _REVISION_PROMPT.format(
                goal=goal,
                title=task.title,
                description=task.description,
                criteria=_bullets(task.acceptance_criteria),
                context=context or "(none)",
                previous=previous_result,
                score=critique.score,
                issues=_bullets(critique.issues),
                required_changes=_bullets(critique.required_changes),
                reasoning=critique.reasoning or "(none given)",
                attempt=task.retry_count + 1,
                max_attempts=self._max_attempts,
            )
        else:
            prompt = _TASK_PROMPT.format(
                goal=goal,
                title=task.title,
                description=task.description,
                criteria=_bullets(task.acceptance_criteria),
                context=context or "(none)",
            )

        result = await agent.invoke_async(prompt)
        return AgentOutcome(
            text=extract_text(result),
            tool_calls=telemetry.tool_calls,
            usage=extract_usage(result),
            stop_reason=getattr(result, "stop_reason", None),
        )


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (none)"
