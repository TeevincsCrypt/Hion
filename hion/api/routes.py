"""HTTP routes for missions, events and approvals."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from hion.api.deps import Container, container_of
from hion.api.schemas import (
    ApprovalDecision,
    ApprovalView,
    CreateMissionRequest,
    EventView,
    MissionSummary,
    MissionView,
)
from hion.domain.enums import EventType
from hion.domain.models import MissionEvent, MissionMetrics
from hion.errors import ApprovalNotFound, ConfigurationError, MissionNotFound
from hion.llm.preflight import check_provider
from hion.orchestration.metrics import compute_metrics
from hion.tools.risk import RISK_POLICY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

Deps = Annotated[Container, Depends(container_of)]

#: How long an idle SSE connection waits before emitting a keepalive comment.
_SSE_HEARTBEAT_SECONDS = 15.0


@router.post("/missions", response_model=MissionView, status_code=status.HTTP_201_CREATED)
async def create_mission(body: CreateMissionRequest, deps: Deps) -> MissionView:
    """Start a mission. Returns immediately; the mission runs in the background."""
    mission = await deps.engine.start_mission(body.goal.strip())
    return MissionView.of(mission)


@router.get("/missions", response_model=list[MissionSummary])
async def list_missions(deps: Deps, limit: int = Query(default=50, ge=1, le=200)) -> list[MissionSummary]:
    """List missions, most recent first."""
    return [MissionSummary.of(m) for m in deps.store.list(limit=limit)]


@router.get("/missions/{mission_id}", response_model=MissionView)
async def get_mission(mission_id: str, deps: Deps) -> MissionView:
    """Retrieve a mission's full current state."""
    return MissionView.of(_mission_or_404(deps, mission_id))


@router.get("/missions/{mission_id}/metrics", response_model=MissionMetrics)
async def get_mission_metrics(mission_id: str, deps: Deps) -> MissionMetrics:
    """Mission statistics.

    Finished missions return the metrics computed when they ended; a running
    mission returns a live snapshot of the same shape.
    """
    mission = _mission_or_404(deps, mission_id)
    return mission.metrics or compute_metrics(mission)


@router.get("/missions/{mission_id}/events", response_model=list[EventView])
async def get_mission_events(
    mission_id: str,
    deps: Deps,
    after: int = Query(default=0, ge=0, description="Return only events after this sequence number."),
) -> list[EventView]:
    """Retrieve a mission's recorded events, oldest first."""
    mission = _mission_or_404(deps, mission_id)
    return [EventView.of(e) for e in mission.events if e.sequence > after]


@router.get("/missions/{mission_id}/events/stream")
async def stream_mission_events(
    mission_id: str,
    deps: Deps,
    after: int = Query(default=0, ge=0),
) -> StreamingResponse:
    """Server-sent events feed of a mission's activity.

    Replays everything recorded so far, then streams live. Subscribing before the
    replay means an event fired mid-replay is delivered rather than dropped.
    """
    mission = _mission_or_404(deps, mission_id)

    async def publisher() -> AsyncIterator[str]:
        async with deps.bus.subscription(mission_id) as queue:
            delivered = after
            for event in list(mission.events):
                if event.sequence > delivered:
                    delivered = event.sequence
                    yield _sse(event)

            while True:
                if mission.is_terminal and queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_SSE_HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if event.sequence <= delivered:
                    continue
                delivered = event.sequence
                yield _sse(event)

    return StreamingResponse(
        publisher(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/approvals", response_model=list[ApprovalView])
async def list_approvals(
    deps: Deps,
    mission_id: str | None = Query(default=None),
) -> list[ApprovalView]:
    """List approval requests still waiting on a human."""
    pending = deps.approvals.pending()
    if mission_id:
        pending = [r for r in pending if r.mission_id == mission_id]
    return [ApprovalView.of(r) for r in pending]


@router.post("/approvals/{approval_id}", response_model=ApprovalView)
async def decide_approval(approval_id: str, body: ApprovalDecision, deps: Deps) -> ApprovalView:
    """Grant or reject a pending approval, resuming the suspended mission."""
    try:
        request = deps.approvals.resolve(
            approval_id,
            approved=body.approved,
            decided_by=body.decided_by,
            note=body.note,
        )
    except ApprovalNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ApprovalView.of(request)


@router.get("/health")
async def health(deps: Deps) -> dict[str, object]:
    """Liveness plus the configuration the process is actually running with."""
    settings = deps.settings
    provider: str
    model_id: str | None
    try:
        provider = settings.resolve_provider()
        model_id = settings.resolve_model_id(provider)
        configured = True
        detail = "A model provider is configured. Call /api/health/provider to verify it answers."
    except ConfigurationError as exc:
        provider, model_id, configured, detail = settings.model_provider, None, False, str(exc)

    return {
        "status": "ok" if configured else "misconfigured",
        "model_provider": provider,
        "model_id": model_id,
        "provider_configured": configured,
        "detail": detail,
        "max_revisions": settings.max_revisions,
        "on_revisions_exhausted": settings.on_revisions_exhausted,
        "auto_approve_max_risk": settings.auto_approve_max_risk.value,
        "critic_approval_threshold": settings.critic_approval_threshold,
        "critic_min_dimension_score": settings.critic_min_dimension_score,
        "event_types": [e.value for e in EventType],
    }


@router.get("/health/provider")
async def provider_health(deps: Deps) -> dict[str, object]:
    """Make one real call to the model provider and report whether it worked.

    This is the check that distinguishes "credentials are present" from
    "credentials work". It costs one tiny completion.
    """
    try:
        model = deps.model_factory()
    except ConfigurationError as exc:
        return {
            "provider": deps.settings.model_provider,
            "model_id": deps.settings.model_id,
            "reachable": False,
            "detail": str(exc),
        }
    status = await check_provider(model, deps.settings)
    return status.as_dict()


@router.get("/risk-policy")
async def risk_policy(deps: Deps) -> dict[str, object]:
    """The risk tiers the Guardian's tool gate actually enforces."""
    return {
        "tiers": RISK_POLICY,
        "auto_approve_max_risk": deps.settings.auto_approve_max_risk.value,
        "high_always_requires_approval": True,
        "unknown_tools_are_high": True,
    }


def _mission_or_404(deps: Container, mission_id: str):
    try:
        return deps.store.get(mission_id)
    except MissionNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _sse(event: MissionEvent) -> str:
    """Format one mission event as an SSE frame."""
    payload = EventView.of(event).model_dump(mode="json")
    return f"id: {event.sequence}\nevent: {event.type.value}\ndata: {json.dumps(payload)}\n\n"
