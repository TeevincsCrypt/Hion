"""Static risk policy for tool calls.

The Guardian agent reasons about what a *task* will cause. This table is what
actually happens to a *tool call*: it is applied mechanically by
:class:`hion.hooks.guardian_gate.GuardianToolGate` before the tool runs, so a
model cannot talk its way past it.

The tiers:

``LOW``
    Reading, searching, analysis, drafting, generating new local artifacts.
    Reversible, confined to the mission workspace, no effect outside Hion.

``MEDIUM``
    Modifying an artifact that already exists, destructive local operations, and
    anything else that could materially change work the user already has.

``HIGH``
    Publishing, sending messages or email, financial actions, deleting important
    data, and any other external side effect.

Unknown actions are HIGH. A tool nobody has classified is a tool nobody has
reasoned about, and the safe reading of "unclassified" is "dangerous".
"""

from __future__ import annotations

from hion.domain.enums import RiskLevel

#: Tool name -> minimum risk level of invoking it.
TOOL_RISK: dict[str, RiskLevel] = {
    # LOW - read, search, analyse, draft, create new local artifacts.
    "web_search": RiskLevel.LOW,
    "fetch_url": RiskLevel.LOW,
    "read_file": RiskLevel.LOW,
    "list_files": RiskLevel.LOW,
    "load_dataset": RiskLevel.LOW,
    "write_file": RiskLevel.LOW,
    "save_dataset": RiskLevel.LOW,
    # MEDIUM - change or destroy work that already exists.
    "update_file": RiskLevel.MEDIUM,
    "delete_file": RiskLevel.MEDIUM,
    # HIGH - anything that leaves Hion.
    "publish_external": RiskLevel.HIGH,
}

#: Risk applied to a tool that is not in the table. Unknown means dangerous.
DEFAULT_TOOL_RISK = RiskLevel.HIGH

#: Human-readable description of each tier, surfaced through the API so a UI and
#: an operator are reading the same policy the gate enforces.
RISK_POLICY: dict[str, dict[str, object]] = {
    RiskLevel.LOW.value: {
        "description": "Read, search, analyse, draft, generate local artifacts.",
        "tools": sorted(name for name, risk in TOOL_RISK.items() if risk is RiskLevel.LOW),
    },
    RiskLevel.MEDIUM.value: {
        "description": "Modify existing artifacts, destructive local operations, "
        "anything that could materially change the user's work.",
        "tools": sorted(name for name, risk in TOOL_RISK.items() if risk is RiskLevel.MEDIUM),
    },
    RiskLevel.HIGH.value: {
        "description": "Publishing, sending messages or email, financial actions, "
        "deleting important data, any external side effect. Always requires a human.",
        "tools": sorted(name for name, risk in TOOL_RISK.items() if risk is RiskLevel.HIGH),
        "unknown_tools": "Any tool not listed above is treated as HIGH.",
    },
}


def risk_for_tool(tool_name: str) -> RiskLevel:
    """Risk level of a tool call by name. Unclassified tools are HIGH."""
    return TOOL_RISK.get(tool_name, DEFAULT_TOOL_RISK)
