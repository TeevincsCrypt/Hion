"""Guardian enforcement inside the Strands event loop.

The Guardian agent's verdict is advice; this hook is the enforcement. It runs on
``BeforeToolCallEvent`` and cancels any tool call whose static risk exceeds the
ceiling a human actually approved for the current task. Because it sits in the
SDK's tool pipeline, no amount of model persuasion routes around it - a blocked
call comes back to the model as a tool error explaining why.
"""

from __future__ import annotations

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

from hion.domain.enums import AgentName, EventType, RiskLevel
from hion.events.recorder import MissionRecorder
from hion.hooks._sdk import is_sdk_internal_tool
from hion.tools.risk import TOOL_RISK, risk_for_tool


class GuardianToolGate(HookProvider):
    """Blocks tool calls above the approved risk ceiling for a task."""

    def __init__(
        self,
        recorder: MissionRecorder,
        agent: AgentName,
        approved_ceiling: RiskLevel,
        task_id: str | None = None,
    ) -> None:
        self._recorder = recorder
        self._agent = agent
        self._ceiling = approved_ceiling
        self._task_id = task_id
        self.blocked: list[str] = []

    @property
    def approved_ceiling(self) -> RiskLevel:
        return self._ceiling

    def register_hooks(self, registry: HookRegistry, **_: object) -> None:
        registry.add_callback(BeforeToolCallEvent, self._gate)

    def _gate(self, event: BeforeToolCallEvent) -> None:
        tool_name = event.tool_use["name"]
        if is_sdk_internal_tool(event.agent, tool_name):
            # SDK machinery, not a mission action. Hion registers no dynamic tools
            # of its own, so this cannot be used to smuggle one past the gate.
            return

        risk = risk_for_tool(tool_name)
        if risk <= self._ceiling:
            return

        reason = (
            f"Guardian blocked '{tool_name}': it is a {risk.value}-risk action but only "
            f"{self._ceiling.value}-risk actions are approved for this task. "
            "Do not retry it. Complete what you can and state clearly in your result that "
            f"'{tool_name}' requires human approval."
        )
        event.cancel_tool = reason
        self.blocked.append(tool_name)
        self._recorder.emit(
            EventType.TOOL_BLOCKED,
            message=f"Guardian blocked {tool_name} ({risk.value} > {self._ceiling.value})",
            task_id=self._task_id,
            agent=self._agent,
            status="blocked",
            tool_name=tool_name,
            risk_level=risk,
            error=reason,
            approved_ceiling=self._ceiling.value,
            unclassified_tool=tool_name not in TOOL_RISK,
        )
