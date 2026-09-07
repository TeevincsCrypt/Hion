"""Executor tests: real side effects, real containment."""

from __future__ import annotations

import json

import pytest

from hion.domain.enums import AgentName, RiskLevel
from hion.tools.context import ExecutionContext
from hion.tools.registry import build_tools_for
from hion.tools.risk import DEFAULT_TOOL_RISK, risk_for_tool


@pytest.fixture
def ctx(settings) -> ExecutionContext:
    return ExecutionContext(mission_id="msn_test", settings=settings)


def _tools(agent: AgentName, ctx: ExecutionContext) -> dict:
    return {t.tool_name: t for t in build_tools_for(agent, ctx)}


def test_workspace_is_sandboxed(ctx):
    with pytest.raises(ValueError, match="escapes the mission workspace"):
        ctx.resolve("../../etc/passwd")
    with pytest.raises(ValueError, match="escapes the mission workspace"):
        ctx.resolve("/etc/passwd")
    assert ctx.resolve("notes/brief.md").is_relative_to(ctx.workspace)


def test_write_read_and_update_a_file(ctx):
    tools = _tools(AgentName.CREATOR, ctx)

    created = tools["write_file"](path="brief.md", content="draft")
    assert created["status"] == "ok"
    assert (ctx.workspace / "brief.md").read_text() == "draft"

    # Creating over an existing file is refused; that is what update_file is for.
    assert tools["write_file"](path="brief.md", content="oops")["status"] == "error"

    updated = tools["update_file"](path="brief.md", content="final")
    assert updated["status"] == "ok"
    assert updated["previous_bytes"] == 5
    assert (ctx.workspace / "brief.md").read_text() == "final"

    assert tools["read_file"](path="brief.md")["content"] == "final"
    assert tools["read_file"](path="nope.md")["status"] == "error"
    assert tools["update_file"](path="nope.md", content="x")["status"] == "error"


def test_datasets_round_trip(ctx):
    tools = _tools(AgentName.RESEARCH, ctx)
    rows = [{"name": "Otter.ai", "price": 17}, {"name": "Granola", "price": 18}]

    saved = tools["save_dataset"](name="competitors", rows=rows)
    assert saved == {"status": "ok", "name": "competitors", "rows": 2, "columns": ["name", "price"]}
    assert json.loads((ctx.workspace / "data" / "competitors.json").read_text()) == rows

    assert tools["load_dataset"](name="competitors")["rows"] == rows
    assert tools["load_dataset"](name="missing")["status"] == "error"


def test_list_files_reports_what_is_there(ctx):
    tools = _tools(AgentName.CREATOR, ctx)
    assert tools["list_files"]()["count"] == 0
    tools["write_file"](path="a/b.md", content="x")
    listing = tools["list_files"]()
    assert listing["count"] == 1
    assert listing["files"][0]["path"] == "a/b.md"


async def test_search_reports_failure_instead_of_inventing_results(ctx):
    """With no backend configured the tool errors; it never returns plausible fiction."""
    tools = _tools(AgentName.RESEARCH, ctx)
    result = await tools["web_search"](query="ai meeting assistants")
    assert result["status"] == "error"
    assert "search backend" in result["error"]


async def test_fetch_url_rejects_non_http_schemes(ctx):
    tools = _tools(AgentName.RESEARCH, ctx)
    result = await tools["fetch_url"](url="file:///etc/passwd")
    assert result["status"] == "error"


async def test_publishing_without_a_destination_fails_loudly(ctx):
    """An unconfigured external channel must not report success."""
    tools = _tools(AgentName.CREATOR, ctx)
    result = await tools["publish_external"](
        channel="stakeholders", subject="Brief", body="..."
    )
    assert result["status"] == "error"
    assert "nothing was published" in result["error"]


def test_capabilities_are_scoped_per_role(ctx):
    assert "publish_external" in _tools(AgentName.CREATOR, ctx)
    assert "publish_external" not in _tools(AgentName.RESEARCH, ctx)
    assert "publish_external" not in _tools(AgentName.ANALYST, ctx)
    assert "web_search" not in _tools(AgentName.CREATOR, ctx)
    # Judges do not act.
    assert build_tools_for(AgentName.CRITIC, ctx) == []
    assert build_tools_for(AgentName.GUARDIAN, ctx) == []
    assert build_tools_for(AgentName.COMMANDER, ctx) == []


def test_risk_policy_defaults_to_dangerous():
    assert risk_for_tool("read_file") is RiskLevel.LOW
    assert risk_for_tool("update_file") is RiskLevel.MEDIUM
    assert risk_for_tool("publish_external") is RiskLevel.HIGH
    assert risk_for_tool("some_future_tool") is DEFAULT_TOOL_RISK is RiskLevel.HIGH


def test_risk_levels_are_ordered():
    assert RiskLevel.LOW < RiskLevel.MEDIUM < RiskLevel.HIGH
    assert RiskLevel.max(RiskLevel.LOW, RiskLevel.HIGH, RiskLevel.MEDIUM) is RiskLevel.HIGH
