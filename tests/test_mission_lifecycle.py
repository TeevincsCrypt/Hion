"""End-to-end proof of the mission lifecycle.

Everything below runs through real Strands agents, real tool execution and real
hooks. Only the model provider is scripted, so the assertions are about Hion's
orchestration rather than about a language model's mood on the day.
"""

from __future__ import annotations

import asyncio

import pytest

from hion.domain.enums import AgentName, EventType, MissionStatus, RiskLevel, TaskStatus
from tests.support import scenarios
from tests.support.scripted_model import ScriptedModel


async def _run_reference_mission(container, *, approve: bool = True):
    """Start the reference mission and answer its approval request."""
    mission = await container.engine.start_mission(scenarios.GOAL)
    decided = await _decide_next_approval(container, mission.id, approved=approve)
    assert decided, "the mission never asked for human approval"
    await container.engine.wait_for(mission.id)
    return mission


async def _decide_next_approval(container, mission_id: str, *, approved: bool) -> bool:
    """Wait for the mission to suspend on an approval, then answer it."""
    for _ in range(200):
        pending = [r for r in container.approvals.pending() if r.mission_id == mission_id]
        if pending:
            container.approvals.resolve(
                pending[0].id, approved=approved, decided_by="test-human", note="decided in test"
            )
            return True
        await asyncio.sleep(0.01)
    return False


async def test_full_mission_lifecycle(make_container):
    """Plan -> research -> analyse -> approve -> create -> critique -> revise -> deliver."""
    container, model = make_container(scenarios.reference_script())
    mission = await _run_reference_mission(container)

    assert mission.status is MissionStatus.COMPLETED
    assert mission.final_result == scenarios.FINAL_BRIEF
    assert mission.objective == scenarios.PLAN.objective

    # The Commander's plan became a real dependency graph.
    assert [t.assigned_agent for t in mission.tasks] == [
        AgentName.RESEARCH,
        AgentName.ANALYST,
        AgentName.CREATOR,
    ]
    research, analysis, brief = mission.tasks
    assert research.dependencies == []
    assert analysis.dependencies == [research.id]
    assert brief.dependencies == [analysis.id]
    assert all(t.status is TaskStatus.COMPLETED for t in mission.tasks)

    # Every agent in the crew actually ran through Strands.
    assert set(model.calls) == {"commander", "guardian", "research", "analyst", "creator", "critic"}


async def test_critic_rejection_drives_a_revision(make_container):
    """A rejected result goes back to the specialist with the critique attached."""
    container, model = make_container(scenarios.reference_script())
    mission = await _run_reference_mission(container)

    brief = mission.tasks[-1]
    assert brief.retry_count == 1
    assert brief.critique is not None and brief.critique.approved
    assert brief.critique.score == 91
    assert len(brief.runs) == 2, "the Creator should have produced a draft and a revision"
    assert brief.runs[0].output == scenarios.DRAFT_BRIEF
    assert brief.runs[1].output == scenarios.FINAL_BRIEF

    # The revision prompt carried the Critic's required changes to the Creator.
    creator_prompts = [text for role, text in model.prompts if role == "creator"]
    revision_prompt = creator_prompts[-1]
    for change in scenarios.REJECT_DRAFT.required_changes:
        assert change in revision_prompt
    assert scenarios.DRAFT_BRIEF in revision_prompt


async def test_guardian_blocks_an_unapproved_high_risk_tool(make_container):
    """The Creator's attempt to publish externally is stopped inside the tool pipeline."""
    container, _ = make_container(scenarios.reference_script())
    mission = await _run_reference_mission(container)

    blocked = [e for e in mission.events if e.type is EventType.TOOL_BLOCKED]
    assert len(blocked) == 1
    assert blocked[0].data["tool_name"] == "publish_external"
    assert blocked[0].data["tool_risk"] == RiskLevel.HIGH.value
    assert blocked[0].data["approved_ceiling"] == RiskLevel.MEDIUM.value

    # Nothing was published, and the tool call is recorded as blocked, not as done.
    brief = mission.tasks[-1]
    publish_calls = [c for run in brief.runs for c in run.tool_calls if c.tool_name == "publish_external"]
    assert [c.status for c in publish_calls] == ["blocked"]


async def test_tools_produce_real_artifacts(make_container, settings):
    """The executor writes real files; nothing is simulated."""
    container, _ = make_container(scenarios.reference_script())
    mission = await _run_reference_mission(container)

    workspace = settings.mission_workspace(mission.id)
    dataset = workspace / "data" / "competitors.json"
    brief = workspace / "brief.md"

    assert dataset.is_file(), "the Research agent's save_dataset call should have written a file"
    assert "Otter.ai" in dataset.read_text()
    assert brief.is_file()
    assert brief.read_text() == scenarios.FINAL_BRIEF, "the revision should have updated the artifact"


async def test_approval_rejection_fails_the_task(make_container):
    """A human 'no' stops the work rather than being reasoned around."""
    script = scenarios.reference_script()
    script["creator"] = []  # the Creator must never run
    container, _ = make_container(script)

    mission = await container.engine.start_mission(scenarios.GOAL)
    assert await _decide_next_approval(container, mission.id, approved=False)
    await container.engine.wait_for(mission.id)

    brief = mission.tasks[-1]
    assert brief.status is TaskStatus.FAILED
    assert brief.runs == []
    assert any(e.type is EventType.APPROVAL_REJECTED for e in mission.events)
    # The upstream work still completed, so the mission delivers what it could.
    assert mission.status is MissionStatus.COMPLETED
    assert mission.tasks[0].status is TaskStatus.COMPLETED


async def test_mission_suspends_while_waiting_for_a_human(make_container):
    """WAITING_FOR_APPROVAL is a real suspension, not a status label."""
    container, _ = make_container(scenarios.reference_script())
    mission = await container.engine.start_mission(scenarios.GOAL)

    for _ in range(200):
        if mission.status is MissionStatus.WAITING_FOR_APPROVAL:
            break
        await asyncio.sleep(0.01)

    assert mission.status is MissionStatus.WAITING_FOR_APPROVAL
    pending = container.approvals.pending()
    assert len(pending) == 1
    assert pending[0].risk_level is RiskLevel.MEDIUM
    assert mission.tasks[-1].status is TaskStatus.WAITING_FOR_APPROVAL
    assert mission.tasks[-1].runs == []

    container.approvals.resolve(pending[0].id, approved=True, decided_by="test-human", note=None)
    await container.engine.wait_for(mission.id)
    assert mission.status is MissionStatus.COMPLETED


async def test_event_stream_records_the_whole_mission(make_container):
    """Every phase is observable from the event log alone."""
    container, _ = make_container(scenarios.reference_script())
    mission = await _run_reference_mission(container)

    types = [e.type for e in mission.events]
    for required in (
        EventType.MISSION_CREATED,
        EventType.MISSION_PLANNED,
        EventType.TASK_CREATED,
        EventType.GUARDIAN_REVIEW,
        EventType.APPROVAL_REQUIRED,
        EventType.APPROVAL_GRANTED,
        EventType.TASK_STARTED,
        EventType.AGENT_STARTED,
        EventType.TOOL_STARTED,
        EventType.TOOL_COMPLETED,
        EventType.TOOL_BLOCKED,
        EventType.AGENT_COMPLETED,
        EventType.CRITIC_STARTED,
        EventType.CRITIC_COMPLETED,
        EventType.REVISION_REQUESTED,
        EventType.TASK_RETRYING,
        EventType.TASK_COMPLETED,
        EventType.MISSION_COMPLETED,
    ):
        assert required in types, f"missing {required.value}"

    assert types[0] is EventType.MISSION_CREATED
    assert types[-1] is EventType.MISSION_COMPLETED
    assert [e.sequence for e in mission.events] == list(range(1, len(mission.events) + 1))

    # Events carry enough structure for a UI to render them without re-deriving state.
    planned = next(e for e in mission.events if e.type is EventType.MISSION_PLANNED)
    assert planned.data["task_count"] == 3
    approval = next(e for e in mission.events if e.type is EventType.APPROVAL_REQUIRED)
    assert approval.data["approval_id"].startswith("apr_")
    assert approval.task_id == mission.tasks[-1].id


async def test_live_subscribers_receive_events_as_they_happen(make_container):
    """The bus feeds Mission Control while the mission is still running."""
    container, _ = make_container(scenarios.reference_script())
    mission = await container.engine.start_mission(scenarios.GOAL)

    received = []
    async with container.bus.subscription(mission.id) as queue:
        approver = asyncio.create_task(_decide_next_approval(container, mission.id, approved=True))
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=5.0)
            received.append(event)
            if event.type is EventType.MISSION_COMPLETED:
                break
        await approver

    assert [e.type for e in received][-1] is EventType.MISSION_COMPLETED
    assert EventType.APPROVAL_REQUIRED in {e.type for e in received}


async def test_revision_budget_is_finite(make_container):
    """A Critic that never approves cannot loop the mission forever."""
    script = scenarios.reference_script()
    script["creator"] = [scenarios.DRAFT_BRIEF] * 4
    script["critic"] = [scenarios.APPROVE, scenarios.APPROVE] + [scenarios.REJECT_DRAFT] * 3
    container, _ = make_container(script)

    mission = await _run_reference_mission(container)
    brief = mission.tasks[-1]

    assert brief.retry_count == 2  # max_revisions
    assert len(brief.runs) == 3  # original + two revisions
    assert brief.status is TaskStatus.COMPLETED  # on_revisions_exhausted="accept"
    assert brief.critique is not None and not brief.critique.approved

    exhausted = [e for e in mission.events if e.type is EventType.REVISION_EXHAUSTED]
    assert len(exhausted) == 1
    completed = next(
        e for e in mission.events if e.type is EventType.TASK_COMPLETED and e.task_id == brief.id
    )
    assert completed.data["degraded"] is True


async def test_revision_budget_can_fail_the_task_instead(make_container):
    """With on_revisions_exhausted='fail', unapproved work does not ship."""
    script = scenarios.reference_script()
    script["creator"] = [scenarios.DRAFT_BRIEF] * 4
    script["critic"] = [scenarios.APPROVE, scenarios.APPROVE] + [scenarios.REJECT_DRAFT] * 3
    container, _ = make_container(script, on_revisions_exhausted="fail")

    mission = await _run_reference_mission(container)
    assert mission.tasks[-1].status is TaskStatus.FAILED


@pytest.mark.parametrize("failing_role", ["research"])
async def test_agent_failure_is_contained(make_container, failing_role):
    """An exploding agent fails its task and blocks dependents, not the process."""
    script = scenarios.reference_script()
    script[failing_role] = []  # exhausting the script raises inside the agent
    container, _ = make_container(script)

    mission = await container.engine.start_mission(scenarios.GOAL)
    await container.engine.wait_for(mission.id)

    assert mission.tasks[0].status is TaskStatus.FAILED
    assert mission.tasks[1].status is TaskStatus.FAILED  # blocked by its dependency
    assert mission.status is MissionStatus.FAILED
    assert any(e.type is EventType.AGENT_FAILED for e in mission.events)


async def test_scripted_model_is_only_the_provider(make_container):
    """Sanity check that the double is a genuine Strands model, not a stubbed agent."""
    from strands.models.model import Model

    _, model = make_container(scenarios.reference_script())
    assert isinstance(model, Model)
    assert isinstance(model, ScriptedModel)
