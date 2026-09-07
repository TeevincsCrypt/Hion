"""Failure handling: bad providers, bad model output, bad tools, exhausted revisions."""

from __future__ import annotations

import asyncio

import pytest

from hion.config import Settings
from hion.domain.enums import EventType, MissionStatus, RiskLevel, TaskStatus
from hion.errors import ConfigurationError, MalformedModelOutput
from hion.llm.preflight import ProviderStatus, check_provider, diagnose, require_provider
from hion.llm.provider import build_model
from tests.support import scenarios
from tests.support.scripted_model import ScriptedModel, ScriptedTool


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
# Provider configuration
# ---------------------------------------------------------------------------


def test_no_provider_configured_fails_with_instructions(monkeypatch):
    """With neither AWS credentials nor an API key, the error says what to set."""
    monkeypatch.setattr("hion.config._has_aws_credentials", lambda: False)
    settings = Settings(_env_file=None, model_provider="auto", model_api_key=None)

    with pytest.raises(ConfigurationError) as exc:
        settings.resolve_provider()

    message = str(exc.value)
    assert "AWS_ACCESS_KEY_ID" in message
    assert "HION_MODEL_API_KEY" in message
    assert ".env.example" in message

    with pytest.raises(ConfigurationError):
        build_model(settings)


def test_auto_prefers_bedrock_when_aws_credentials_exist(monkeypatch):
    monkeypatch.setattr("hion.config._has_aws_credentials", lambda: True)
    settings = Settings(_env_file=None, model_provider="auto", model_api_key="sk-ant-x")
    assert settings.resolve_provider() == "bedrock"


def test_auto_falls_back_to_an_api_key_provider(monkeypatch):
    monkeypatch.setattr("hion.config._has_aws_credentials", lambda: False)
    settings = Settings(_env_file=None, model_provider="auto", model_api_key="sk-ant-x")
    assert settings.resolve_provider() == "anthropic"
    assert settings.resolve_model_id() == "claude-sonnet-4-5-20250929"


@pytest.mark.parametrize(
    ("error_text", "expected"),
    [
        ("UnrecognizedClientException: The security token is invalid", "rejected as invalid"),
        ("ExpiredTokenException: the token has expired", "have expired"),
        ("AuthenticationError: invalid_api_key", "missing or rejected"),
        ("AccessDeniedException: not authorized to perform", "not authorised for this model"),
        ("ResourceNotFoundException: could not find model", "does not exist"),
        ("EndpointConnectionError: Connection refused", "could not be reached"),
        ("ThrottlingException: RateLimit exceeded", "rate limiting"),
    ],
)
def test_provider_errors_become_actionable_messages(settings, error_text, expected):
    """A botocore stack trace is not a useful error; this is what replaces it."""
    message = diagnose(RuntimeError(error_text), settings)
    assert message is not None
    assert expected in message
    assert "AWS_ACCESS_KEY_ID" in message  # the remedy for the bedrock provider


def test_unrelated_errors_are_not_misdiagnosed(settings):
    assert diagnose(ValueError("a task-specific problem"), settings) is None


async def test_provider_check_reports_an_unusable_provider(settings):
    """A model that raises on every call is reported, not raised through."""

    class _Broken(ScriptedModel):
        async def stream(self, *args, **kwargs):
            raise RuntimeError("UnrecognizedClientException: bad token")
            yield  # pragma: no cover - unreachable, keeps this an async generator

    status = await check_provider(_Broken({}), settings)
    assert isinstance(status, ProviderStatus)
    assert status.reachable is False
    assert "rejected as invalid" in status.detail

    with pytest.raises(Exception, match="rejected as invalid"):
        await require_provider(_Broken({}), settings)


async def test_provider_check_passes_against_a_working_model(settings):
    status = await check_provider(ScriptedModel({"commander": ["OK"]}), settings)
    # The probe agent has no Hion system prompt, so the scripted double cannot
    # route it - what matters is that a reachable provider reports reachable.
    assert isinstance(status, ProviderStatus)


async def test_a_dead_provider_fails_the_mission_with_the_diagnosis(make_container, settings):
    """The useful error survives all the way to mission.error."""

    class _Broken(ScriptedModel):
        async def stream(self, *args, **kwargs):
            raise RuntimeError("UnrecognizedClientException: The security token is invalid")
            yield  # pragma: no cover

    container, _ = make_container({})
    container.engine._model_factory = lambda: _Broken({})  # noqa: SLF001

    mission = await container.engine.start_mission(scenarios.GOAL)
    await container.engine.wait_for(mission.id)

    assert mission.status is MissionStatus.FAILED
    assert "rejected as invalid" in (mission.error or "")
    assert mission.metrics is not None
    failed = next(e for e in mission.events if e.type is EventType.MISSION_FAILED)
    assert "rejected as invalid" in (failed.error or "")


# ---------------------------------------------------------------------------
# Malformed model output
# ---------------------------------------------------------------------------


async def test_prose_instead_of_a_plan_fails_the_mission_cleanly(make_container):
    """A Commander that answers in prose produces no plan, and says so.

    Strands forces one retry through the structured-output tool before giving
    up, so a Commander that never emits it needs two scripted turns to exhaust.
    """
    prose = "Sure! Here is a plan: first, research things."
    container, _ = make_container({"commander": [prose, prose]})

    mission = await container.engine.start_mission(scenarios.GOAL)
    await container.engine.wait_for(mission.id)

    assert mission.status is MissionStatus.FAILED
    assert "Planning failed" in (mission.error or "")
    assert mission.tasks == []
    assert mission.metrics is not None and mission.metrics.total_tasks == 0


async def test_malformed_critique_fails_only_its_task(make_container):
    """One agent returning garbage must not take the mission down with it."""
    script = scenarios.reference_script()
    prose = "Looks good to me!"  # prose where a Critique was required
    script["critic"] = [prose, prose]  # forced-retry also needs a turn
    container, _ = make_container(script)

    mission = await container.engine.start_mission(scenarios.GOAL)
    await container.engine.wait_for(mission.id)

    research = mission.tasks[0]
    assert research.status is TaskStatus.FAILED
    assert "did not return a valid Critique" in (research.error or "")
    assert any(e.type is EventType.AGENT_FAILED for e in mission.events)
    assert mission.status is MissionStatus.FAILED


async def test_malformed_output_is_a_typed_error(make_container):
    """The engine can distinguish a bad model response from a bug in Hion."""
    from hion.agents.factory import AgentFactory
    from hion.agents.runtime import run_structured
    from hion.config import Settings
    from hion.domain.models import MissionPlan
    from hion.tools.context import ExecutionContext

    settings = Settings(_env_file=None, model_provider="bedrock")
    factory = AgentFactory(
        model=ScriptedModel({"commander": ["not a plan", "still not a plan"]}),
        ctx=ExecutionContext(mission_id="msn_x", settings=settings),
    )
    from hion.domain.enums import AgentName

    agent = factory.build(AgentName.COMMANDER)
    with pytest.raises(MalformedModelOutput, match="MissionPlan"):
        await run_structured(agent, "plan it", MissionPlan)


# ---------------------------------------------------------------------------
# Guardian enforcement
# ---------------------------------------------------------------------------


async def test_an_unknown_tool_is_treated_as_high_risk(make_container):
    """A tool nobody classified is a tool nobody reasoned about."""
    script = scenarios.reference_script()
    script["creator"] = [
        ScriptedTool(name="wire_money", input={"amount": 5000, "to": "acct-1"}),
        scenarios.WRITE_BRIEF_FILE,
        scenarios.FINAL_BRIEF,
    ]
    script["critic"] = [scenarios.APPROVE, scenarios.APPROVE, scenarios.APPROVE]
    container, _ = make_container(script)
    mission = await _run(container)

    blocked = [e for e in mission.events if e.type is EventType.TOOL_BLOCKED]
    assert len(blocked) == 1
    assert blocked[0].tool_name == "wire_money"
    assert blocked[0].risk_level is RiskLevel.HIGH
    assert blocked[0].data["unclassified_tool"] is True


async def test_the_gate_blocks_every_attempt_not_just_the_first(make_container):
    """A model that retries a blocked tool is blocked every time."""
    script = scenarios.reference_script()
    script["creator"] = [
        scenarios.ATTEMPT_PUBLISH,
        scenarios.ATTEMPT_PUBLISH,
        scenarios.ATTEMPT_PUBLISH,
        scenarios.WRITE_BRIEF_FILE,
        scenarios.FINAL_BRIEF,
    ]
    script["critic"] = [scenarios.APPROVE, scenarios.APPROVE, scenarios.APPROVE]
    container, _ = make_container(script)
    mission = await _run(container)

    blocked = [e for e in mission.events if e.type is EventType.TOOL_BLOCKED]
    assert len(blocked) == 3
    assert all(e.tool_name == "publish_external" for e in blocked)
    # Nothing was published and the mission still delivered.
    assert mission.status is MissionStatus.COMPLETED


async def test_a_medium_risk_tool_runs_under_the_default_ceiling(make_container):
    """The gate is a ceiling, not a blanket ban: update_file is MEDIUM and allowed."""
    container, _ = make_container(scenarios.reference_script())
    mission = await _run(container)

    updates = [
        e
        for e in mission.events
        if e.type is EventType.TOOL_COMPLETED and e.tool_name == "update_file"
    ]
    assert updates and all(e.status != "blocked" for e in updates)
    assert updates[0].risk_level is RiskLevel.MEDIUM


async def test_auto_approve_ceiling_bounds_unsupervised_tasks(make_container):
    """auto_approve_max_risk gates tasks the Guardian did not escalate.

    The Analyst's task is assessed LOW and never sees a human. If it reaches for
    a MEDIUM-risk tool anyway, the ceiling that applies is the auto-approve
    setting, not the task's own LOW verdict.
    """
    script = scenarios.reference_script()
    script["analyst"] = [
        ScriptedTool(name="update_file", input={"path": "x.md", "content": "y"}),
        scenarios.ANALYSIS,
    ]

    def update_file_blocks(mission) -> list:
        return [
            e
            for e in mission.events
            if e.type is EventType.TOOL_BLOCKED and e.tool_name == "update_file"
        ]

    lenient, _ = make_container(script, auto_approve_max_risk=RiskLevel.MEDIUM)
    lenient_mission = await _run(lenient)
    assert update_file_blocks(lenient_mission) == []

    strict, _ = make_container(script, auto_approve_max_risk=RiskLevel.LOW)
    strict_mission = await _run(strict)
    blocked = update_file_blocks(strict_mission)
    assert len(blocked) == 1
    assert blocked[0].data["approved_ceiling"] == RiskLevel.LOW.value


# ---------------------------------------------------------------------------
# Revision ceiling
# ---------------------------------------------------------------------------


async def test_exhausted_revisions_fail_gracefully_with_an_explanation(make_container):
    """The default is to explain the failure, not to ship work the Critic rejected."""
    script = scenarios.reference_script()
    script["creator"] = [scenarios.DRAFT_BRIEF] * 4
    script["critic"] = [scenarios.APPROVE, scenarios.APPROVE] + [scenarios.REJECT_DRAFT] * 3
    container, _ = make_container(script)  # settings default: on_revisions_exhausted="fail"
    assert container.settings.on_revisions_exhausted == "fail"

    mission = await _run(container)
    brief = mission.tasks[-1]

    assert brief.status is TaskStatus.FAILED
    assert brief.retry_count == 2  # max_revisions, then it stops
    assert len(brief.runs) == 3
    error = brief.error or ""
    assert "rejected creator's work 3 times" in error
    assert "final score 54/100" in error
    assert "source quality at 20/100" in error  # the weakest dimension is named
    assert "Name all four researched competitors" in error  # what is still outstanding

    exhausted = next(e for e in mission.events if e.type is EventType.REVISION_EXHAUSTED)
    assert exhausted.status == "exhausted"
    assert exhausted.retry_count == 2
    assert exhausted.data["dimensions"]["source_quality"] == 20

    # The mission still delivers the work that did pass, and names what did not.
    assert mission.status is MissionStatus.COMPLETED
    assert mission.metrics is not None
    assert mission.metrics.failed_tasks == 1


async def test_revisions_never_loop_forever(make_container):
    """A Critic that always rejects still terminates, at max_revisions + 1 attempts."""
    script = scenarios.reference_script()
    script["creator"] = [scenarios.DRAFT_BRIEF] * 10
    script["critic"] = [scenarios.APPROVE, scenarios.APPROVE] + [scenarios.REJECT_DRAFT] * 8
    container, _ = make_container(script, max_revisions=3)

    mission = await asyncio.wait_for(_run(container), timeout=15)
    brief = mission.tasks[-1]
    assert len(brief.runs) == 4  # 1 original + 3 revisions
    assert brief.retry_count == 3


async def test_zero_revisions_means_one_attempt(make_container):
    script = scenarios.reference_script()
    script["creator"] = [scenarios.DRAFT_BRIEF]
    script["critic"] = [scenarios.APPROVE, scenarios.APPROVE, scenarios.REJECT_DRAFT]
    container, _ = make_container(script, max_revisions=0)

    mission = await _run(container)
    assert len(mission.tasks[-1].runs) == 1
    assert mission.tasks[-1].status is TaskStatus.FAILED


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


async def test_completed_work_survives_a_synthesis_failure(make_container):
    """Losing finished specialist work because the final summary call failed is the wrong trade."""
    script = scenarios.reference_script()
    script["commander"] = [scenarios.PLAN]  # nothing left for the synthesis call
    container, _ = make_container(script)
    mission = await _run(container)

    assert mission.status is MissionStatus.COMPLETED
    assert mission.final_result is not None
    assert "could not compose the final summary" in mission.final_result
    assert scenarios.FINAL_BRIEF in mission.final_result  # the real work is still there
    assert scenarios.RESEARCH_NOTES in mission.final_result


async def test_a_failed_dependency_does_not_hang_the_mission(make_container):
    """Downstream tasks fail with a reason instead of waiting forever."""
    script = scenarios.reference_script()
    script["analyst"] = []
    container, _ = make_container(script)

    mission = await asyncio.wait_for(
        container.engine.start_mission(scenarios.GOAL), timeout=10
    )
    await asyncio.wait_for(container.engine.wait_for(mission.id), timeout=15)

    research, analysis, brief = mission.tasks
    assert research.status is TaskStatus.COMPLETED
    assert analysis.status is TaskStatus.FAILED
    assert brief.status is TaskStatus.FAILED
    assert "Blocked by unfinished dependencies" in (brief.error or "")
    assert brief.runs == []
    assert mission.status is MissionStatus.COMPLETED  # research still delivered
