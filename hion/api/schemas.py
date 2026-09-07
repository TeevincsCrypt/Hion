"""Request and response bodies for the Hion HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from hion.domain.enums import AgentName, MissionStatus, RiskLevel, TaskStatus
from hion.domain.models import (
    ApprovalRequest,
    Critique,
    GuardianVerdict,
    Mission,
    MissionEvent,
    MissionMetrics,
    Task,
)


class CreateMissionRequest(BaseModel):
    goal: str = Field(min_length=8, max_length=4000, description="The outcome Hion should achieve.")


class TaskView(BaseModel):
    id: str
    key: str
    title: str
    description: str
    assigned_agent: AgentName
    status: TaskStatus
    dependencies: list[str]
    acceptance_criteria: list[str]
    result: str | None
    critique: Critique | None
    guardian_verdict: GuardianVerdict | None
    retry_count: int
    error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, task: Task) -> TaskView:
        return cls(**task.model_dump(exclude={"mission_id", "runs"}))


class EventView(BaseModel):
    id: str
    mission_id: str
    sequence: int
    type: str
    task_id: str | None
    agent: AgentName | None
    message: str
    status: str | None
    duration_ms: int | None
    retry_count: int | None
    tool_name: str | None
    risk_level: RiskLevel | None
    error: str | None
    result_summary: str | None
    data: dict[str, Any]
    created_at: datetime

    @classmethod
    def of(cls, event: MissionEvent) -> EventView:
        payload = event.model_dump()
        payload["type"] = event.type.value
        return cls(**payload)


class MissionView(BaseModel):
    id: str
    goal: str
    status: MissionStatus
    objective: str | None
    success_criteria: list[str]
    tasks: list[TaskView]
    results: dict[str, str]
    approvals: list[ApprovalRequest]
    final_result: str | None
    error: str | None
    metrics: MissionMetrics | None
    event_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, mission: Mission) -> MissionView:
        return cls(
            id=mission.id,
            goal=mission.goal,
            status=mission.status,
            objective=mission.objective,
            success_criteria=mission.success_criteria,
            tasks=[TaskView.of(task) for task in mission.tasks],
            results=mission.results,
            approvals=mission.approvals,
            final_result=mission.final_result,
            error=mission.error,
            metrics=mission.metrics,
            event_count=len(mission.events),
            created_at=mission.created_at,
            updated_at=mission.updated_at,
        )


class MissionSummary(BaseModel):
    id: str
    goal: str
    status: MissionStatus
    task_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, mission: Mission) -> MissionSummary:
        return cls(
            id=mission.id,
            goal=mission.goal,
            status=mission.status,
            task_count=len(mission.tasks),
            created_at=mission.created_at,
            updated_at=mission.updated_at,
        )


class ApprovalDecision(BaseModel):
    approved: bool
    decided_by: str = Field(default="human", max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class ApprovalView(BaseModel):
    id: str
    mission_id: str
    task_id: str | None
    action: str
    risk_level: RiskLevel
    rationale: str
    status: str
    requested_at: datetime
    resolved_at: datetime | None
    decided_by: str | None
    note: str | None

    @classmethod
    def of(cls, request: ApprovalRequest) -> ApprovalView:
        return cls(**request.model_dump())
