"""Per-mission execution context shared by every tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hion.config import Settings
from hion.domain.enums import AgentName


@dataclass(slots=True)
class ExecutionContext:
    """Everything a tool needs to act on behalf of one mission.

    Tools are built per mission so the filesystem sandbox and the audit trail are
    bound to the mission that owns them; nothing is global.
    """

    mission_id: str
    settings: Settings
    agent: AgentName | None = None

    @property
    def workspace(self) -> Path:
        root = self.settings.mission_workspace(self.mission_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def resolve(self, relative_path: str) -> Path:
        """Resolve a caller-supplied path inside the mission sandbox.

        Raises:
            ValueError: the path escapes the mission workspace.
        """
        root = self.workspace
        candidate = (root / relative_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(
                f"Path {relative_path!r} escapes the mission workspace. "
                "Use a relative path inside the mission directory."
            )
        return candidate
