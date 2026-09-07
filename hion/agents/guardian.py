"""The Guardian: decides what a human has to sign off on."""

from __future__ import annotations

import logging

from hion.agents.factory import AgentFactory
from hion.agents.runtime import run_structured
from hion.config import Settings
from hion.domain.enums import AgentName, RiskLevel
from hion.domain.models import GuardianVerdict, Task
from hion.events.recorder import MissionRecorder
from hion.hooks.telemetry import MissionTelemetryHook

logger = logging.getLogger(__name__)

_ASSESS_PROMPT = """\
Classify the risk of executing this task.

MISSION GOAL
------------
{goal}

TASK
----
Title: {title}
Assigned to: {agent}
Instruction: {description}

TOOLS AVAILABLE TO THAT AGENT
-----------------------------
{tools}

Decide the risk level and whether a human must approve before this task runs.
"""


class Guardian:
    """Assesses task risk and produces approval requirements."""

    def __init__(self, factory: AgentFactory, recorder: MissionRecorder, settings: Settings) -> None:
        self._factory = factory
        self._recorder = recorder
        self._settings = settings

    async def assess(self, *, goal: str, task: Task) -> GuardianVerdict:
        """Judge a task's risk, then apply Hion's non-negotiable policy on top."""
        tools = self._factory.tools_for(task.assigned_agent)
        tool_names = ", ".join(sorted(t.tool_name for t in tools)) or "(none)"

        hook = MissionTelemetryHook(self._recorder, AgentName.GUARDIAN, task_id=task.id)
        agent = self._factory.build(AgentName.GUARDIAN, hooks=[hook])
        verdict = await run_structured(
            agent,
            _ASSESS_PROMPT.format(
                goal=goal,
                title=task.title,
                agent=task.assigned_agent.value,
                description=task.description,
                tools=tool_names,
            ),
            GuardianVerdict,
        )
        return self.apply_policy(verdict)

    def apply_policy(self, verdict: GuardianVerdict) -> GuardianVerdict:
        """Hion's own rules override the model's judgement, never the reverse.

        HIGH risk always requires a human, whatever the model concluded and
        whatever ``auto_approve_max_risk`` is set to. Below HIGH, the configured
        ceiling decides.
        """
        requires = (
            verdict.requires_human_approval
            or verdict.risk_level is RiskLevel.HIGH
            or verdict.risk_level > self._settings.auto_approve_max_risk
        )
        if requires == verdict.requires_human_approval:
            return verdict
        return verdict.model_copy(update={"requires_human_approval": requires})
