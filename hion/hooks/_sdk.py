"""Telling Hion's tools apart from the SDK's own machinery.

Strands implements structured output as a tool: it registers a synthetic tool
named after the Pydantic model, calls it, and unregisters it. That call is not a
mission action - it must not appear in the activity stream as one, and it must
not be judged by the Guardian's risk policy, where an unclassified name would be
treated as HIGH and blocked.

Dynamic registration is the distinguishing mark. Hion registers no dynamic tools
of its own, so anything in the agent's ``dynamic_tools`` is the SDK's. Note that
``AgentTool.is_dynamic`` is *not* usable for this: ``register_dynamic_tool`` does
not call ``mark_dynamic``, so the flag stays False on the structured-output tool.
"""

from __future__ import annotations

from typing import Any


def is_sdk_internal_tool(agent: Any, tool_name: str) -> bool:
    """Whether ``tool_name`` is a tool the SDK registered, not one Hion provides."""
    registry = getattr(agent, "tool_registry", None)
    dynamic = getattr(registry, "dynamic_tools", None) or {}
    return tool_name in dynamic
