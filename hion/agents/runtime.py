"""Running a Strands agent and capturing what it did."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel
from strands import Agent
from strands.agent.agent_result import AgentResult
from strands.types.exceptions import StructuredOutputException

from hion.domain.models import ToolCallRecord
from hion.errors import MalformedModelOutput

T = TypeVar("T", bound=BaseModel)


@dataclass(slots=True)
class AgentOutcome:
    """The result of one agent invocation, flattened for the engine."""

    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    stop_reason: str | None = None


def extract_text(result: AgentResult) -> str:
    """Concatenate the text blocks of an agent's final message.

    Only ``text`` blocks are read. Reasoning content is deliberately dropped here
    rather than filtered later, so model reasoning cannot reach a task result,
    the event log, or the API.
    """
    message = result.message or {}
    parts = [block["text"] for block in message.get("content", []) if "text" in block]
    return "\n".join(part.strip() for part in parts if part.strip()).strip()


def extract_usage(result: AgentResult) -> dict[str, int]:
    usage = getattr(getattr(result, "metrics", None), "accumulated_usage", None)
    if not usage:
        return {}
    return {
        "input_tokens": int(usage.get("inputTokens", 0)),
        "output_tokens": int(usage.get("outputTokens", 0)),
        "total_tokens": int(usage.get("totalTokens", 0)),
    }


async def run_structured(agent: Agent, prompt: str, output_model: type[T]) -> T:
    """Invoke an agent and require a schema-valid structured result.

    Strands implements structured output as a synthetic tool inside the normal
    event loop, so this goes through the same pipeline (and the same hooks) as
    any other agent call.

    A model that answers in prose, stops early, or emits a payload that fails
    schema validation produces no structured output. That is a model failure, not
    a crash: it is raised as a typed error the engine turns into a task failure
    with an explanation.

    Raises:
        MalformedModelOutput: the agent finished without a schema-valid result.
    """
    try:
        result = await agent.invoke_async(prompt, structured_output_model=output_model)
    except StructuredOutputException as exc:
        # The SDK raises this directly when the model still won't call the
        # structured-output tool after being forced to retry once.
        raise MalformedModelOutput(
            f"{agent.name or 'agent'} did not return a valid {output_model.__name__}: {exc}"
        ) from exc

    output = getattr(result, "structured_output", None)
    if not isinstance(output, output_model):
        raise MalformedModelOutput(
            f"{agent.name or 'agent'} did not return a valid {output_model.__name__} "
            f"(stop_reason={getattr(result, 'stop_reason', None)!r}). "
            "The model answered without calling the structured-output tool, or its "
            "payload failed schema validation."
        )
    return output
