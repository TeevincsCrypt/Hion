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
from hion.domain.models import MissionEvent
from hion.errors import ApprovalNotFound, MissionNotFound

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
    return {
        "status": "ok",
        "model_provider": deps.settings.model_provider,
        "model_id": deps.settings.model_id,
        "max_revisions": deps.settings.max_revisions,
        "auto_approve_max_risk": deps.settings.auto_approve_max_risk.value,
        "event_types": [e.value for e in EventType],
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
