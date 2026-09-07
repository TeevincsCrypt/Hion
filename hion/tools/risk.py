"""Static risk policy for tool calls.

The Guardian agent reasons about task-level risk, but reasoning alone is not
enforcement. This table is the floor: it is applied mechanically by
:class:`hion.hooks.guardian_gate.GuardianToolGate` before any tool runs, so a
model cannot talk its way past it.
"""

from __future__ import annotations

from hion.domain.enums import RiskLevel

#: Tool name -> minimum risk level of invoking it.
TOOL_RISK: dict[str, RiskLevel] = {
    # Read-only information gathering.
    "web_search": RiskLevel.LOW,
    "fetch_url": RiskLevel.LOW,
    "read_file": RiskLevel.LOW,
    "list_files": RiskLevel.LOW,
    "load_dataset": RiskLevel.LOW,
    # Creating new artifacts inside the mission sandbox.
    "write_file": RiskLevel.LOW,
    "save_dataset": RiskLevel.LOW,
    # Mutating something that already exists.
    "update_file": RiskLevel.MEDIUM,
    "delete_file": RiskLevel.MEDIUM,
    # Anything leaving the system.
    "publish_external": RiskLevel.HIGH,
}

#: Risk applied to a tool that is not in the table. Unknown means dangerous.
DEFAULT_TOOL_RISK = RiskLevel.HIGH


def risk_for_tool(tool_name: str) -> RiskLevel:
    """Risk level of a tool call by name."""
    return TOOL_RISK.get(tool_name, DEFAULT_TOOL_RISK)
