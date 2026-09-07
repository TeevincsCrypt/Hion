"""Unit tests for plan validation, Guardian policy and critique normalisation."""

from __future__ import annotations

import pytest

from hion.agents.commander import _validate_plan
from hion.agents.critic import _normalise
from hion.agents.guardian import Guardian
from hion.domain.enums import AgentName, RiskLevel
from hion.domain.models import Critique, GuardianVerdict, MissionPlan, PlannedTask
from hion.errors import PlanningError


def _plan(*tasks: PlannedTask) -> MissionPlan:
    return MissionPlan(objective="o", success_criteria=[], tasks=list(tasks))


def _task(key: str, agent: AgentName = AgentName.RESEARCH, depends_on: list[str] | None = None):
    return PlannedTask(
        key=key,
        title=key,
        description=f"do {key}",
        assigned_agent=agent,
        depends_on=depends_on or [],
    )


def test_a_sound_plan_validates():
    _validate_plan(_plan(_task("a"), _task("b", AgentName.CREATOR, ["a"])))


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


def test_a_rejection_always_carries_something_to_fix():
    critique = _normalise(Critique(approved=False, score=40, issues=["vague"], required_changes=[]))
    assert critique.required_changes == ["vague"]

    bare = _normalise(Critique(approved=False, score=40, issues=[], required_changes=[]))
    assert len(bare.required_changes) == 1


def test_an_approval_with_required_changes_is_not_an_approval():
    critique = _normalise(Critique(approved=True, score=80, required_changes=["cite sources"]))
    assert critique.approved is False
