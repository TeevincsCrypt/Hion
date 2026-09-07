"""Unit tests for plan validation, Guardian policy and critique normalisation."""

from __future__ import annotations

import pytest

from hion.agents.commander import MAX_TASKS, _validate_plan
from hion.agents.critic import Critic
from hion.agents.guardian import Guardian
from hion.domain.enums import AgentName, RiskLevel
from hion.domain.models import (
    Critique,
    CritiqueDimensions,
    GuardianVerdict,
    MissionPlan,
    PlannedTask,
)
from hion.errors import PlanningError


def _plan(*tasks: PlannedTask) -> MissionPlan:
    return MissionPlan(objective="o", success_criteria=[], tasks=list(tasks))


#: Long enough to pass the "no vague descriptions" rule, so tests exercise the
#: rule they are actually about.
def _description(key: str) -> str:
    return f"Carry out {key} in full, covering every required element and stating what done looks like."


def _task(
    key: str,
    agent: AgentName = AgentName.RESEARCH,
    depends_on: list[str] | None = None,
    *,
    title: str | None = None,
    description: str | None = None,
    criteria: list[str] | None = None,
):
    return PlannedTask(
        key=key,
        title=title or key,
        description=description if description is not None else _description(key),
        assigned_agent=agent,
        depends_on=depends_on or [],
        acceptance_criteria=criteria if criteria is not None else [f"{key} is complete"],
    )


def _critic(settings) -> Critic:
    """A Critic with only its calibration rules wired up - normalise() is pure."""
    critic = Critic.__new__(Critic)
    critic._settings = settings  # noqa: SLF001
    return critic


def test_a_sound_plan_validates_without_warnings():
    warnings = _validate_plan(_plan(_task("research"), _task("write", AgentName.CREATOR, ["research"])))
    assert warnings == []


def test_oversized_plans_are_rejected():
    tasks = [_task(f"t{i}") for i in range(MAX_TASKS + 1)]
    with pytest.raises(PlanningError, match="decomposed too finely"):
        _validate_plan(_plan(*tasks))


def test_vague_descriptions_are_rejected():
    """The description is the whole instruction, so an empty one is unrunnable."""
    with pytest.raises(PlanningError, match="no usable instruction"):
        _validate_plan(_plan(_task("a", description="Research it.")))


def test_near_duplicate_tasks_are_flagged():
    warnings = _validate_plan(
        _plan(
            _task("research_competitors", title="Research the top competitors"),
            _task("gather_competitors", title="Research competitors"),
        )
    )
    assert any("look like the same work" in w for w in warnings)


def test_a_deliverable_with_no_dependencies_is_flagged():
    """A writer with no declared inputs will work blind."""
    warnings = _validate_plan(_plan(_task("research"), _task("write", AgentName.CREATOR)))
    assert any("declares no dependencies" in w for w in warnings)


def test_missing_acceptance_criteria_is_flagged():
    warnings = _validate_plan(_plan(_task("a", criteria=[])))
    assert any("no acceptance criteria" in w for w in warnings)


def test_empty_plans_are_rejected():
    with pytest.raises(PlanningError, match="no tasks"):
        _validate_plan(_plan())


def test_duplicate_keys_are_rejected():
    with pytest.raises(PlanningError, match="duplicate task keys"):
        _validate_plan(_plan(_task("a"), _task("a")))


def test_dangling_dependencies_are_rejected():
    with pytest.raises(PlanningError, match="unknown task"):
        _validate_plan(_plan(_task("a", depends_on=["ghost"])))


def test_self_dependency_is_rejected():
    with pytest.raises(PlanningError, match="depends on itself"):
        _validate_plan(_plan(_task("a", depends_on=["a"])))


def test_cycles_are_rejected_before_execution():
    """A cyclic plan would deadlock the engine, so it never gets to run."""
    with pytest.raises(PlanningError, match="dependency cycle"):
        _validate_plan(
            _plan(
                _task("a", depends_on=["c"]),
                _task("b", depends_on=["a"]),
                _task("c", depends_on=["b"]),
            )
        )


def test_tasks_cannot_be_delegated_to_non_specialists():
    with pytest.raises(PlanningError, match="not a delegatable specialist"):
        _validate_plan(_plan(_task("a", AgentName.CRITIC)))


@pytest.mark.parametrize(
    ("risk", "model_says", "expected"),
    [
        (RiskLevel.LOW, False, False),
        (RiskLevel.MEDIUM, False, False),
        (RiskLevel.MEDIUM, True, True),
        (RiskLevel.HIGH, False, True),  # policy overrides the model
        (RiskLevel.HIGH, True, True),
    ],
)
def test_high_risk_always_needs_a_human(settings, risk, model_says, expected):
    guardian = Guardian.__new__(Guardian)
    guardian._settings = settings  # noqa: SLF001 - policy is pure, no agent needed
    verdict = guardian.apply_policy(
        GuardianVerdict(risk_level=risk, requires_human_approval=model_says, rationale="r")
    )
    assert verdict.requires_human_approval is expected


def test_a_stricter_ceiling_escalates_medium_risk(settings):
    guardian = Guardian.__new__(Guardian)
    guardian._settings = settings.model_copy(update={"auto_approve_max_risk": RiskLevel.LOW})  # noqa: SLF001
    verdict = guardian.apply_policy(
        GuardianVerdict(risk_level=RiskLevel.MEDIUM, requires_human_approval=False, rationale="r")
    )
    assert verdict.requires_human_approval is True


def test_a_rejection_always_carries_something_to_fix(settings):
    critic = _critic(settings)
    critique = critic.normalise(
        Critique(approved=False, score=40, issues=["vague"], required_changes=[])
    )
    assert critique.required_changes == ["vague"]

    bare = critic.normalise(Critique(approved=False, score=40, issues=[], required_changes=[]))
    assert len(bare.required_changes) == 1


def test_an_approval_with_required_changes_is_not_an_approval(settings):
    critique = _critic(settings).normalise(
        Critique(approved=True, score=80, required_changes=["cite sources"])
    )
    assert critique.approved is False


def test_a_low_score_cannot_be_approved(settings):
    """The Critic does not get to approve work it scored below the threshold."""
    critique = _critic(settings).normalise(Critique(approved=True, score=60, required_changes=[]))
    assert critique.approved is False
    assert any("below the 75 approval threshold" in change for change in critique.required_changes)


def test_a_strong_average_cannot_hide_a_failing_dimension(settings):
    """Fabricated claims are not offset by a well-written document."""
    critique = _critic(settings).normalise(
        Critique(
            approved=True,
            score=88,
            required_changes=[],
            dimensions=CritiqueDimensions(
                factual_support=30,
                completeness=95,
                consistency=95,
                task_compliance=95,
                source_quality=95,
                actionable_usefulness=95,
            ),
        )
    )
    assert critique.approved is False
    assert any("factual support" in change for change in critique.required_changes)


def test_a_genuinely_good_result_is_still_approved(settings):
    """Calibration tightens approval; it does not make approval impossible."""
    critique = _critic(settings).normalise(
        Critique(
            approved=True,
            score=91,
            required_changes=[],
            dimensions=CritiqueDimensions(
                factual_support=90,
                completeness=92,
                consistency=95,
                task_compliance=90,
                source_quality=88,
                actionable_usefulness=90,
            ),
        )
    )
    assert critique.approved is True
    assert critique.required_changes == []
