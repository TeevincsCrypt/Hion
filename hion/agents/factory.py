"""Construction of the Strands agents that make up the Hion crew.

Every Hion agent is a genuine ``strands.Agent``: same model provider, same event
loop, same tool pipeline. What differs per role is the system prompt, the tools
it is allowed to touch, and the hooks attached to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from strands import Agent
from strands.hooks import HookProvider
from strands.models.model import Model

from hion.agents.prompts import description_for, system_prompt_for
from hion.domain.enums import AgentName
from hion.tools.context import ExecutionContext
from hion.tools.registry import build_tools_for


@dataclass(slots=True)
class AgentFactory:
    """Builds role-specific Strands agents for one mission."""

    model: Model
    ctx: ExecutionContext
    _tool_cache: dict[AgentName, list] = field(default_factory=dict)

    def tools_for(self, agent: AgentName) -> list:
        """Tools for a role, built once per mission so file handles stay stable."""
        if agent not in self._tool_cache:
            self._tool_cache[agent] = build_tools_for(agent, self.ctx)
        return self._tool_cache[agent]

    def build(
        self,
        agent: AgentName,
        *,
        hooks: list[HookProvider] | None = None,
        extra_system_prompt: str = "",
    ) -> Agent:
        """Create a fresh Strands agent for a role.

        A new instance per invocation keeps conversation state scoped to a single
        task attempt, which is what makes revisions reproducible.
        """
        system_prompt = system_prompt_for(agent)
        if extra_system_prompt:
            system_prompt = f"{system_prompt}\n{extra_system_prompt}"

        return Agent(
            model=self.model,
            name=f"hion-{agent.value}",
            description=description_for(agent),
            system_prompt=system_prompt,
            tools=self.tools_for(agent),
            hooks=list(hooks or []),
            callback_handler=None,
        )
