"""Core mission data model.

These are the objects that flow through the orchestration engine and out of the
HTTP API. The structured-output contracts (``MissionPlan``, ``Critique``,
``GuardianVerdict``) are handed directly to Strands
``Agent.structured_output_async`` so the models are constrained by the schema
rather than by prompt-level pleading for JSON.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from hion.domain.enums import AgentName, EventType, MissionStatus, RiskLevel, TaskStatus


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Structured-output contracts (LLM-facing schemas)
# ---------------------------------------------------------------------------


class PlannedTask(BaseModel):
    """One task in the Commander's plan.

    ``key`` is a short slug the Commander uses to wire up ``depends_on``; the
    engine maps keys onto generated task ids.
    """

    key: str = Field(description="Short unique slug for this task, e.g. 'research_competitors'.")
    title: str = Field(description="Short imperative title of the task.")
    description: str = Field(
        description=(
            "Precise, self-contained instruction for the assigned agent, including what "
            "'done' looks like and what the deliverable should contain."
        )
    )
    assigned_agent: AgentName = Field(
        description="Which specialist performs this task: research, creator, or analyst."
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Keys of tasks that must complete before this one starts.",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Concrete, checkable conditions the Critic will evaluate the result against.",
    )


class MissionPlan(BaseModel):
    """The Commander's decomposition of a goal into an executable task graph."""

    objective: str = Field(description="One-sentence restatement of the desired outcome.")
    success_criteria: list[str] = Field(
        default_factory=list, description="What must be true for the mission to count as done."
    )
    tasks: list[PlannedTask] = Field(description="Ordered task graph, 2-6 tasks.")


class Critique(BaseModel):
    """The Critic's structured evaluation of another agent's result."""

    approved: bool = Field(description="True only if the result genuinely completes the task.")
    score: int = Field(ge=0, le=100, description="Overall quality score from 0 to 100.")
    issues: list[str] = Field(
        default_factory=list,
        description="Specific defects found: incorrect claims, contradictions, gaps, unsupported assertions.",
    )
    required_changes: list[str] = Field(
        default_factory=list,
        description="Concrete, actionable changes the responsible agent must make. Empty if approved.",
    )
    reasoning: str = Field(default="", description="Brief justification for the verdict.")


class GuardianVerdict(BaseModel):
    """The Guardian's structured approval requirement for an action."""

    risk_level: RiskLevel = Field(description="LOW, MEDIUM or HIGH.")
    requires_human_approval: bool = Field(description="Whether a human must approve before proceeding.")
    rationale: str = Field(description="Why this risk level was assigned.")
    irreversible: bool = Field(default=False, description="True if the action cannot be undone.")
    external_side_effects: bool = Field(
        default=False, description="True if the action affects systems or people outside Hion."
    )


# ---------------------------------------------------------------------------
# Runtime records
# ---------------------------------------------------------------------------


class ToolCallRecord(BaseModel):
    """A tool invocation made by an agent during a task."""

    tool_name: str
    tool_use_id: str
    agent: AgentName
    status: str = "ok"
    blocked_reason: str | None = None
    duration_ms: int | None = None
    started_at: datetime = Field(default_factory=_now)


class AgentRun(BaseModel):
    """One invocation of a specialist agent, including revisions."""

    agent: AgentName
    attempt: int
    output: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    usage: dict[str, int] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """A pending or resolved request for human sign-off."""

    id: str = Field(default_factory=lambda: _new_id("apr"))
    mission_id: str
    task_id: str | None = None
    action: str
    risk_level: RiskLevel
    rationale: str
    status: str = "PENDING"  # PENDING | GRANTED | REJECTED | TIMED_OUT
    requested_at: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = None
    decided_by: str | None = None
    note: str | None = None


class Task(BaseModel):
    """A unit of delegated work inside a mission."""

    id: str = Field(default_factory=lambda: _new_id("tsk"))
    mission_id: str
    key: str
    title: str
    description: str
    assigned_agent: AgentName
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    result: str | None = None
    critique: Critique | None = None
    guardian_verdict: GuardianVerdict | None = None
    retry_count: int = 0
    runs: list[AgentRun] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()


class MissionEvent(BaseModel):
    """An immutable record of something that happened during a mission."""

    id: str = Field(default_factory=lambda: _new_id("evt"))
    mission_id: str
    sequence: int = 0
    type: EventType
    task_id: str | None = None
    agent: AgentName | None = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class Mission(BaseModel):
    """A goal handed to Hion, plus everything that happened while pursuing it."""

    id: str = Field(default_factory=lambda: _new_id("msn"))
    goal: str
    status: MissionStatus = MissionStatus.PLANNING
    objective: str | None = None
    success_criteria: list[str] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    results: dict[str, str] = Field(default_factory=dict)
    events: list[MissionEvent] = Field(default_factory=list)
    approvals: list[ApprovalRequest] = Field(default_factory=list)
    final_result: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def task(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    def task_by_key(self, key: str) -> Task | None:
        return next((t for t in self.tasks if t.key == key), None)

    def approval(self, approval_id: str) -> ApprovalRequest | None:
        return next((a for a in self.approvals if a.id == approval_id), None)

    @property
    def is_terminal(self) -> bool:
        return self.status in (MissionStatus.COMPLETED, MissionStatus.FAILED)
