"""Which tools each agent is allowed to use.

Capability is scoped per role. The Research agent cannot write the final brief,
the Creator cannot publish externally without clearing the Guardian, and the
Critic and Guardian have no tools at all - they judge, they do not act.
"""

from __future__ import annotations

from strands.tools.decorator import DecoratedFunctionTool

from hion.domain.enums import AgentName
from hion.tools.context import ExecutionContext
from hion.tools.external import build_external_tools
from hion.tools.research import build_research_tools
from hion.tools.workspace import build_workspace_tools


def build_tools_for(agent: AgentName, ctx: ExecutionContext) -> list[DecoratedFunctionTool]:
    """Build the toolset for one agent on one mission."""
    workspace = build_workspace_tools(ctx)
    by_name = {t.tool_name: t for t in workspace}

    if agent is AgentName.RESEARCH:
        return build_research_tools(ctx) + [
            by_name["write_file"],
            by_name["read_file"],
            by_name["list_files"],
            by_name["save_dataset"],
            by_name["load_dataset"],
        ]

    if agent is AgentName.ANALYST:
        return build_research_tools(ctx) + [
            by_name["read_file"],
            by_name["list_files"],
            by_name["load_dataset"],
            by_name["save_dataset"],
            by_name["write_file"],
        ]

    if agent is AgentName.CREATOR:
        return [*workspace, *build_external_tools(ctx)]

    # Commander, Critic and Guardian reason over results; they do not act on the world.
    return []
