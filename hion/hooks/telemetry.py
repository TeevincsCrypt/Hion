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


class MissionTelemetryHook(HookProvider):
    """Emits agent.* and tool.* mission events for one agent invocation scope."""

    def __init__(
        self,
        recorder: MissionRecorder,
        agent: AgentName,
        task_id: str | None = None,
    ) -> None:
        self._recorder = recorder
        self._agent = agent
        self._task_id = task_id
        self._tool_started_at: dict[str, float] = {}
        self.tool_calls: list[ToolCallRecord] = []

    def register_hooks(self, registry: HookRegistry, **_: object) -> None:
        registry.add_callback(BeforeInvocationEvent, self._on_start)
        registry.add_callback(AfterInvocationEvent, self._on_end)
        registry.add_callback(BeforeToolCallEvent, self._on_tool_start)
        registry.add_callback(AfterToolCallEvent, self._on_tool_end)

    # -- agent lifecycle ---------------------------------------------------

    def _on_start(self, _: BeforeInvocationEvent) -> None:
        self._recorder.emit(
            EventType.AGENT_STARTED,
            message=f"{self._agent.value} agent started",
            task_id=self._task_id,
            agent=self._agent,
        )

    def _on_end(self, event: AfterInvocationEvent) -> None:
        usage = _usage_of(event)
        self._recorder.emit(
            EventType.AGENT_COMPLETED,
            message=f"{self._agent.value} agent finished",
            task_id=self._task_id,
            agent=self._agent,
            tool_calls=len(self.tool_calls),
            usage=usage,
        )

    # -- tool lifecycle ----------------------------------------------------

    def _on_tool_start(self, event: BeforeToolCallEvent) -> None:
        tool_use_id = event.tool_use["toolUseId"]
        self._tool_started_at[tool_use_id] = time.perf_counter()
        self._recorder.emit(
            EventType.TOOL_STARTED,
            message=f"{self._agent.value} calling {event.tool_use['name']}",
            task_id=self._task_id,
            agent=self._agent,
            tool_name=event.tool_use["name"],
            tool_use_id=tool_use_id,
            tool_input=_summarize_input(event.tool_use.get("input")),
        )

    def _on_tool_end(self, event: AfterToolCallEvent) -> None:
        tool_use_id = event.tool_use["toolUseId"]
        tool_name = event.tool_use["name"]
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
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            status="blocked" if blocked_reason else status,
            duration_ms=duration_ms,
            error=str(event.exception) if event.exception else blocked_reason,
        )


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
