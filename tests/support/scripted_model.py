"""A scripted Strands ``Model`` for deterministic tests.

This is a **test double for the model provider only**. It is not a fake agent
system: the agents, the tool pipeline, the hooks, the structured-output machinery
and the orchestration engine under test are all the real thing. Substituting the
model is what makes the mission lifecycle assertable without a paid API call, in
exactly the way you would substitute an HTTP client in any other test.

Responses are queued per agent role (detected from the system prompt). Each
queued item is one model turn:

* ``str``           - the model answers with text and stops.
* ``BaseModel``     - the model calls the structured-output tool with that value.
* ``ScriptedTool``  - the model calls a real tool, then continues to the next item.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from collections.abc import AsyncGenerator, AsyncIterable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

T = TypeVar("T", bound=BaseModel)

#: Marker substrings that identify which Hion agent is calling.
_ROLE_MARKERS: tuple[tuple[str, str], ...] = (
    ("You are the Commander of Hion", "commander"),
    ("You are the Research specialist", "research"),
    ("You are the Analyst specialist", "analyst"),
    ("You are the Creator specialist", "creator"),
    ("You are the Critic of Hion", "critic"),
    ("You are the Guardian of Hion", "guardian"),
)


@dataclass(frozen=True)
class ScriptedTool:
    """A scripted call to one of Hion's real tools."""

    name: str
    input: dict[str, Any] = field(default_factory=dict)


class ScriptExhausted(AssertionError):
    """The agent asked for more turns than the test scripted."""


class ScriptedModel(Model):
    """Replays a fixed script of model turns, keyed by agent role."""

    def __init__(self, script: dict[str, list[Any]]) -> None:
        self._queues: dict[str, deque[Any]] = {
            role: deque(turns) for role, turns in script.items()
        }
        self._config: dict[str, Any] = {"model_id": "scripted-test-model"}
        self.calls: dict[str, int] = defaultdict(int)
        self.prompts: list[tuple[str, str]] = []
        self._tool_use_seq = 0

    # -- Model interface ---------------------------------------------------

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        role = _role_of(system_prompt)
        self.calls[role] += 1
        self.prompts.append((role, _last_user_text(messages)))

        turn = self._next_turn(role)
        if isinstance(turn, BaseModel):
            async for event in self._emit_tool_use(type(turn).__name__, turn.model_dump(mode="json")):
                yield event
            return
        if isinstance(turn, ScriptedTool):
            async for event in self._emit_tool_use(turn.name, turn.input):
                yield event
            return
        async for event in self._emit_text(str(turn)):
            yield event

    async def structured_output(
        self, output_model: type[T], prompt: Messages, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        """Legacy structured-output path, kept so the double satisfies ``Model``."""
        role = _role_of(system_prompt)
        self.calls[role] += 1
        turn = self._next_turn(role)
        if not isinstance(turn, output_model):
            raise ScriptExhausted(
                f"Role {role!r} expected a scripted {output_model.__name__}, got {type(turn).__name__}"
            )
        yield {"output": turn}

    # -- internals ---------------------------------------------------------

    def _next_turn(self, role: str) -> Any:
        queue = self._queues.get(role)
        if not queue:
            raise ScriptExhausted(
                f"No scripted turns left for role {role!r}. "
                f"Turn counts so far: {dict(self.calls)}"
            )
        return queue.popleft()

    async def _emit_text(self, text: str) -> AsyncGenerator[StreamEvent, None]:
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield _metadata(len(text))

    async def _emit_tool_use(self, name: str, payload: dict[str, Any]) -> AsyncGenerator[StreamEvent, None]:
        self._tool_use_seq += 1
        tool_use_id = f"scripted-{self._tool_use_seq}"
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": tool_use_id, "name": name}}}}
        yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(payload)}}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}
        yield _metadata(len(json.dumps(payload)))


def _metadata(size: int) -> StreamEvent:
    tokens = max(1, size // 4)
    return {
        "metadata": {
            "usage": {"inputTokens": tokens, "outputTokens": tokens, "totalTokens": tokens * 2},
            "metrics": {"latencyMs": 1},
        }
    }


def _role_of(system_prompt: str | None) -> str:
    text = system_prompt or ""
    for marker, role in _ROLE_MARKERS:
        if marker in text:
            return role
    raise ScriptExhausted(f"Could not identify the calling agent from its system prompt: {text[:120]!r}")


def _last_user_text(messages: Messages) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        parts = [block["text"] for block in message.get("content", []) if "text" in block]
        if parts:
            return "\n".join(parts)
    return ""
