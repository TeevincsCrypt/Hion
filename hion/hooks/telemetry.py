"""Strands hook provider that turns agent internals into mission events.

This is where the Strands event loop becomes observable. Rather than the engine
guessing what an agent did, the SDK tells us: every model invocation and every
tool call is captured as it happens and streamed to Mission Control.
"""

from __future__ import annotations

import time

from strands.hooks import (
    AfterInvocationEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)

from hion.domain.enums import AgentName, EventType
from hion.domain.models import ToolCallRecord
from hion.events.recorder import MissionRecorder
from hion.hooks._sdk import is_sdk_internal_tool
from hion.tools.risk import risk_for_tool


class MissionTelemetryHook(HookProvider):
    """Emits agent.* and tool.* mission events for one agent invocation scope."""

    def __init__(
        self,
        recorder: MissionRecorder,
        agent: AgentName,
        task_id: str | None = None,
        attempt: int | None = None,
    ) -> None:
        self._recorder = recorder
        self._agent = agent
        self._task_id = task_id
        self._attempt = attempt
        self._started_at: float | None = None
        self._tool_started_at: dict[str, float] = {}
        self.tool_calls: list[ToolCallRecord] = []

    def register_hooks(self, registry: HookRegistry, **_: object) -> None:
        # mypy misresolves HookCallback's variance for BeforeInvocationEvent
        # specifically (AfterInvocationEvent and the tool-call events below are
        # unaffected) against this SDK version's stubs; the callback shape matches
        # every other registered event.
        registry.add_callback(BeforeInvocationEvent, self._on_start)  # type: ignore[arg-type]
        registry.add_callback(AfterInvocationEvent, self._on_end)
        registry.add_callback(BeforeToolCallEvent, self._on_tool_start)
        registry.add_callback(AfterToolCallEvent, self._on_tool_end)

    # -- agent lifecycle ---------------------------------------------------

    def _on_start(self, _: BeforeInvocationEvent) -> None:
        self._started_at = time.perf_counter()
        self._recorder.emit(
            EventType.AGENT_STARTED,
            message=f"{self._agent.value} agent started",
            task_id=self._task_id,
            agent=self._agent,
            status="running",
            retry_count=self._attempt,
        )

    def _on_end(self, event: AfterInvocationEvent) -> None:
        self._recorder.emit(
            EventType.AGENT_COMPLETED,
            message=f"{self._agent.value} agent finished",
            task_id=self._task_id,
            agent=self._agent,
            status="completed",
            duration_ms=self._elapsed_ms(),
            retry_count=self._attempt,
            result_summary=_output_text(event),
            tool_calls=len(self.tool_calls),
            tools_used=sorted({call.tool_name for call in self.tool_calls}),
            usage=_usage_of(event),
        )

    # -- tool lifecycle ----------------------------------------------------

    def _on_tool_start(self, event: BeforeToolCallEvent) -> None:
        tool_use_id = event.tool_use["toolUseId"]
        tool_name = event.tool_use["name"]
        if is_sdk_internal_tool(event.agent, tool_name):
            return  # The structured-output tool, not a mission action.
        self._tool_started_at[tool_use_id] = time.perf_counter()
        self._recorder.emit(
            EventType.TOOL_STARTED,
            message=f"{self._agent.value} calling {tool_name}",
            task_id=self._task_id,
            agent=self._agent,
            status="running",
            tool_name=tool_name,
            risk_level=risk_for_tool(tool_name),
            retry_count=self._attempt,
            tool_use_id=tool_use_id,
            tool_input=_summarize_input(event.tool_use.get("input")),
        )

    def _on_tool_end(self, event: AfterToolCallEvent) -> None:
        tool_use_id = event.tool_use["toolUseId"]
        tool_name = event.tool_use["name"]
        if is_sdk_internal_tool(event.agent, tool_name):
            return
        started = self._tool_started_at.pop(tool_use_id, None)
        duration_ms = int((time.perf_counter() - started) * 1000) if started else None
        status = "error" if event.exception else str(event.result.get("status", "success"))
        blocked_reason = event.cancel_message if getattr(event, "cancel_message", None) else None

        self.tool_calls.append(
            ToolCallRecord(
                tool_name=tool_name,
                tool_use_id=tool_use_id,
                agent=self._agent,
                status="blocked" if blocked_reason else status,
                blocked_reason=blocked_reason,
                duration_ms=duration_ms,
            )
        )
        self._recorder.emit(
            EventType.TOOL_COMPLETED,
            message=f"{tool_name} -> {'blocked' if blocked_reason else status}",
            task_id=self._task_id,
            agent=self._agent,
            status="blocked" if blocked_reason else status,
            duration_ms=duration_ms,
            retry_count=self._attempt,
            tool_name=tool_name,
            risk_level=risk_for_tool(tool_name),
            error=str(event.exception) if event.exception else blocked_reason,
            tool_use_id=tool_use_id,
        )


    def _elapsed_ms(self) -> int | None:
        if self._started_at is None:
            return None
        return int((time.perf_counter() - self._started_at) * 1000)


def _output_text(event: AfterInvocationEvent) -> str | None:
    """The agent's text output, for the activity stream.

    Text content blocks only - reasoning blocks are never read, so no hidden
    reasoning can reach the event log.
    """
    message = getattr(getattr(event, "result", None), "message", None) or {}
    parts = [block["text"] for block in message.get("content", []) if "text" in block]
    return "\n".join(parts).strip() or None


def _usage_of(event: AfterInvocationEvent) -> dict[str, int]:
    result = getattr(event, "result", None)
    metrics = getattr(result, "metrics", None)
    usage = getattr(metrics, "accumulated_usage", None)
    if not usage:
        return {}
    return {
        "input_tokens": int(usage.get("inputTokens", 0)),
        "output_tokens": int(usage.get("outputTokens", 0)),
        "total_tokens": int(usage.get("totalTokens", 0)),
    }


def _summarize_input(value: object, limit: int = 400) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}..."
