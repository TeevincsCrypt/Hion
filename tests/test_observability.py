"""Mission metrics, event ordering, and what the activity stream is allowed to carry."""

from __future__ import annotations

import asyncio

from hion.domain.enums import AgentName, EventType, MissionStatus, RiskLevel
from tests.support import scenarios


async def _run(container, *, approve: bool = True):
    mission = await container.engine.start_mission(scenarios.GOAL)
    for _ in range(300):
        pending = [r for r in container.approvals.pending() if r.mission_id == mission.id]
        if pending:
            container.approvals.resolve(
                pending[0].id, approved=approve, decided_by="test-human", note=None
            )
            break
        await asyncio.sleep(0.01)
    await container.engine.wait_for(mission.id)
    return mission


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


async def test_metrics_are_computed_at_completion(make_container):
    container, _ = make_container(scenarios.reference_script())
    mission = await _run(container)

    metrics = mission.metrics
    assert metrics is not None
    assert metrics.total_tasks == 3
    assert metrics.completed_tasks == 3
    assert metrics.failed_tasks == 0
    assert metrics.retries == 1  # the Creator revised once
    assert metrics.revisions_requested == 1
    # commander plan + 3 guardian + 3 specialists + 1 creator revision + 4 critic + commander synth
    assert metrics.agent_invocations == 13
    # Executed only: save_dataset, write_file, update_file. The blocked
    # publish_external is counted as blocked, not as a call that ran.
    assert metrics.tool_calls == 3
    assert metrics.tool_calls_blocked == 1
    assert metrics.approvals_requested == 1
    assert metrics.approvals_granted == 1
    assert metrics.approvals_rejected == 0
    assert metrics.events_recorded == len(mission.events)
    assert metrics.duration_seconds >= 0
    assert metrics.finished_at is not None and metrics.started_at == mission.created_at
    assert metrics.average_critic_score == 91.0
    assert metrics.total_tokens > 0


async def test_metrics_count_a_rejection(make_container):
    script = scenarios.reference_script()
    script["creator"] = []
    container, _ = make_container(script)
    mission = await _run(container, approve=False)

    assert mission.metrics is not None
    assert mission.metrics.approvals_requested == 1
    assert mission.metrics.approvals_rejected == 1
    assert mission.metrics.approvals_granted == 0
    assert mission.metrics.failed_tasks == 1
    assert mission.metrics.completed_tasks == 2


async def test_metrics_exist_on_a_failed_mission(make_container):
    """A mission that produced nothing still reports what it spent getting there."""
    script = scenarios.reference_script()
    script["research"] = []
    container, _ = make_container(script)
    mission = await container.engine.start_mission(scenarios.GOAL)
    await container.engine.wait_for(mission.id)

    assert mission.status is MissionStatus.FAILED
    assert mission.metrics is not None
    assert mission.metrics.completed_tasks == 0
    assert mission.metrics.failed_tasks == 3
    assert mission.metrics.total_tasks == 3


async def test_a_running_mission_reports_a_live_snapshot(make_container):
    """Metrics have the same shape before the mission finishes."""
    from hion.orchestration.metrics import compute_metrics

    container, _ = make_container(scenarios.reference_script())
    mission = await container.engine.start_mission(scenarios.GOAL)
    for _ in range(300):
        if mission.status is MissionStatus.WAITING_FOR_APPROVAL:
            break
        await asyncio.sleep(0.01)

    snapshot = compute_metrics(mission)
    assert mission.metrics is None  # not yet finalised
    assert snapshot.approvals_requested == 1
    assert snapshot.approvals_granted == 0
    assert snapshot.completed_tasks == 2

    pending = container.approvals.pending()
    container.approvals.resolve(pending[0].id, approved=True, decided_by="t", note=None)
    await container.engine.wait_for(mission.id)


# ---------------------------------------------------------------------------
# Event ordering and envelope
# ---------------------------------------------------------------------------


async def test_events_are_contiguously_ordered(make_container):
    container, _ = make_container(scenarios.reference_script())
    mission = await _run(container)

    sequences = [e.sequence for e in mission.events]
    assert sequences == list(range(1, len(mission.events) + 1))
    timestamps = [e.created_at for e in mission.events]
    assert timestamps == sorted(timestamps)
    assert len({e.id for e in mission.events}) == len(mission.events)


async def test_lifecycle_order_is_causal(make_container):
    """A task cannot start before it was planned, or be critiqued before it ran."""
    container, _ = make_container(scenarios.reference_script())
    mission = await _run(container)

    def first(event_type: EventType) -> int:
        return next(e.sequence for e in mission.events if e.type is event_type)

    def last(event_type: EventType) -> int:
        return max(e.sequence for e in mission.events if e.type is event_type)

    assert first(EventType.MISSION_CREATED) < first(EventType.MISSION_PLANNED)
    assert first(EventType.MISSION_PLANNED) < first(EventType.TASK_CREATED)
    assert first(EventType.TASK_CREATED) < first(EventType.GUARDIAN_REVIEW)
    assert first(EventType.GUARDIAN_REVIEW) < first(EventType.TASK_STARTED)
    assert first(EventType.APPROVAL_REQUIRED) < first(EventType.APPROVAL_GRANTED)
    assert first(EventType.AGENT_STARTED) < first(EventType.CRITIC_STARTED)
    assert first(EventType.REVISION_REQUESTED) < first(EventType.TASK_RETRYING)
    assert last(EventType.TASK_COMPLETED) < first(EventType.MISSION_COMPLETED)


async def test_ordering_holds_per_task_under_concurrency(make_container):
    """Interleaved waves must still keep each task's own events in order."""
    container, _ = make_container(scenarios.reference_script())
    mission = await _run(container)

    for task in mission.tasks:
        own = [e for e in mission.events if e.task_id == task.id]
        assert [e.sequence for e in own] == sorted(e.sequence for e in own)
        types = [e.type for e in own]
        assert types.index(EventType.GUARDIAN_REVIEW) < types.index(EventType.TASK_STARTED)


async def test_events_carry_the_ui_envelope(make_container):
    """Mission Control gets its fields on the event, not buried in a payload."""
    container, _ = make_container(scenarios.reference_script())
    mission = await _run(container)

    for event in mission.events:
        assert event.mission_id == mission.id
        assert event.created_at is not None
        assert isinstance(event.type, EventType)

    tool_done = next(e for e in mission.events if e.type is EventType.TOOL_COMPLETED)
    assert tool_done.tool_name and tool_done.risk_level is not None
    assert tool_done.duration_ms is not None and tool_done.status
    assert tool_done.task_id and tool_done.agent

    guardian = next(e for e in mission.events if e.type is EventType.GUARDIAN_REVIEW)
    assert guardian.risk_level is RiskLevel.LOW
    assert guardian.status == "auto_approved"

    agent_done = next(
        e
        for e in mission.events
        if e.type is EventType.AGENT_COMPLETED and e.agent is AgentName.RESEARCH
    )
    assert agent_done.duration_ms is not None
    assert agent_done.result_summary == scenarios.RESEARCH_NOTES

    retrying = next(e for e in mission.events if e.type is EventType.TASK_RETRYING)
    assert retrying.retry_count == 1
    assert retrying.data["attempts_remaining"] == 2

    completed = next(e for e in mission.events if e.type is EventType.MISSION_COMPLETED)
    assert completed.duration_ms is not None
    assert completed.data["metrics"]["completed_tasks"] == 3


async def test_result_summaries_are_bounded(make_container):
    """The event log summarises output; it is not a second copy of every deliverable."""
    from hion.events.recorder import SUMMARY_LIMIT

    long_brief = ("word " * 4000).strip()
    script = scenarios.reference_script()
    script["creator"] = [
        scenarios.ATTEMPT_PUBLISH,
        scenarios.WRITE_BRIEF_FILE,
        long_brief,
        scenarios.UPDATE_BRIEF_FILE,
        long_brief,
    ]
    container, _ = make_container(script)
    mission = await _run(container)

    summaries = [e.result_summary for e in mission.events if e.result_summary]
    assert summaries, "agent output should reach the stream"
    assert all(len(s) <= SUMMARY_LIMIT + 3 for s in summaries)
    assert any(s.endswith("...") for s in summaries)
    # The full text is still on the task, so nothing is lost.
    assert mission.tasks[-1].result == long_brief


async def test_reasoning_content_never_reaches_the_event_log(make_container):
    """Observability is actions and decisions, not private chain-of-thought."""
    from hion.agents.runtime import extract_text

    class _Result:
        message = {
            "role": "assistant",
            "content": [
                {"reasoningContent": {"reasoningText": {"text": "SECRET internal deliberation"}}},
                {"text": "The visible answer."},
            ],
        }

    assert extract_text(_Result()) == "The visible answer."

    container, _ = make_container(scenarios.reference_script())
    mission = await _run(container)
    serialised = "".join(e.model_dump_json() for e in mission.events)
    assert "reasoningContent" not in serialised
