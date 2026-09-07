"""HTTP API tests.

The app is exercised in-process over ASGI on the test's own event loop, so a
mission's background task really does make progress between requests - the same
way it does under uvicorn.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from hion.api.app import create_app
from hion.domain.enums import EventType, MissionStatus
from tests.support import scenarios
from tests.support.scripted_model import ScriptedModel


@pytest.fixture
def api(settings):
    """An ASGI client for a Hion app backed by the reference script."""

    def factory(script: dict[str, list] | None = None):
        model = ScriptedModel(script or scenarios.reference_script())
        app = create_app(settings=settings, model_factory=lambda: model)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://hion.test"
        )
        return client, app

    return factory


async def _await_pending_approval(app, mission_id: str):
    approvals = app.state.container.approvals
    for _ in range(300):
        pending = [r for r in approvals.pending() if r.mission_id == mission_id]
        if pending:
            return pending[0]
        await asyncio.sleep(0.01)
    raise AssertionError("no approval was requested")


async def _await_status(app, mission_id: str, status: MissionStatus):
    mission = app.state.container.store.get(mission_id)
    for _ in range(600):
        if mission.status is status:
            return mission
        await asyncio.sleep(0.01)
    raise AssertionError(f"mission stayed in {mission.status.value}, expected {status.value}")


async def test_create_mission_returns_immediately(api):
    client, app = api()
    async with client:
        response = await client.post("/api/missions", json={"goal": scenarios.GOAL})

        assert response.status_code == 201
        body = response.json()
        assert body["id"].startswith("msn_")
        assert body["goal"] == scenarios.GOAL
        assert body["status"] in (MissionStatus.PLANNING.value, MissionStatus.RUNNING.value)
        assert body["final_result"] is None

        approval = await _await_pending_approval(app, body["id"])
        await client.post(f"/api/approvals/{approval.id}", json={"approved": True})
        await _await_status(app, body["id"], MissionStatus.COMPLETED)


async def test_goal_is_validated(api):
    client, _ = api()
    async with client:
        assert (await client.post("/api/missions", json={"goal": "hi"})).status_code == 422
        assert (await client.post("/api/missions", json={})).status_code == 422


async def test_full_flow_over_http(api):
    """POST a goal, approve what the Guardian escalates, read back the result."""
    client, app = api()
    async with client:
        mission_id = (await client.post("/api/missions", json={"goal": scenarios.GOAL})).json()["id"]

        pending = (await client.get("/api/approvals", params={"mission_id": mission_id})).json()
        if not pending:
            await _await_pending_approval(app, mission_id)
            pending = (await client.get("/api/approvals", params={"mission_id": mission_id})).json()
        assert len(pending) == 1
        assert pending[0]["risk_level"] == "MEDIUM"
        assert pending[0]["status"] == "PENDING"

        decision = await client.post(
            f"/api/approvals/{pending[0]['id']}",
            json={"approved": True, "decided_by": "alex", "note": "ship it"},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "GRANTED"
        assert decision.json()["decided_by"] == "alex"

        await _await_status(app, mission_id, MissionStatus.COMPLETED)

        mission = (await client.get(f"/api/missions/{mission_id}")).json()
        assert mission["status"] == MissionStatus.COMPLETED.value
        assert mission["final_result"] == scenarios.FINAL_BRIEF
        assert len(mission["tasks"]) == 3
        assert mission["tasks"][-1]["retry_count"] == 1
        assert mission["tasks"][-1]["critique"]["approved"] is True
        assert mission["tasks"][-1]["guardian_verdict"]["risk_level"] == "MEDIUM"

        events = (await client.get(f"/api/missions/{mission_id}/events")).json()
        assert events[0]["type"] == EventType.MISSION_CREATED.value
        assert events[-1]["type"] == EventType.MISSION_COMPLETED.value

        after = (
            await client.get(f"/api/missions/{mission_id}/events", params={"after": events[2]["sequence"]})
        ).json()
        assert [e["sequence"] for e in after] == [e["sequence"] for e in events[3:]]


async def test_approval_can_only_be_decided_once(api):
    client, app = api()
    async with client:
        mission_id = (await client.post("/api/missions", json={"goal": scenarios.GOAL})).json()["id"]
        approval = await _await_pending_approval(app, mission_id)

        first = await client.post(f"/api/approvals/{approval.id}", json={"approved": True})
        assert first.status_code == 200
        second = await client.post(f"/api/approvals/{approval.id}", json={"approved": True})
        assert second.status_code == 404

        await _await_status(app, mission_id, MissionStatus.COMPLETED)


async def test_unknown_ids_are_404(api):
    client, _ = api()
    async with client:
        assert (await client.get("/api/missions/msn_missing")).status_code == 404
        assert (await client.get("/api/missions/msn_missing/events")).status_code == 404
        assert (
            await client.post("/api/approvals/apr_missing", json={"approved": True})
        ).status_code == 404


async def test_sse_streams_live_then_closes(api):
    """A client connected mid-mission receives the rest of it and a clean close."""
    client, app = api()
    async with client:
        mission_id = (await client.post("/api/missions", json={"goal": scenarios.GOAL})).json()["id"]

        async def approve() -> None:
            approval = await _await_pending_approval(app, mission_id)
            await client.post(f"/api/approvals/{approval.id}", json={"approved": True})

        approver = asyncio.create_task(approve())
        seen: list[dict] = []
        async with client.stream("GET", f"/api/missions/{mission_id}/events/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    seen.append(json.loads(line.removeprefix("data: ")))
        await approver

    types = [e["type"] for e in seen]
    assert types[0] == EventType.MISSION_CREATED.value
    assert types[-1] == EventType.MISSION_COMPLETED.value
    assert EventType.APPROVAL_REQUIRED.value in types
    assert [e["sequence"] for e in seen] == sorted(e["sequence"] for e in seen)


async def test_sse_replays_a_finished_mission(api):
    client, app = api()
    async with client:
        mission_id = (await client.post("/api/missions", json={"goal": scenarios.GOAL})).json()["id"]
        approval = await _await_pending_approval(app, mission_id)
        await client.post(f"/api/approvals/{approval.id}", json={"approved": True})
        mission = await _await_status(app, mission_id, MissionStatus.COMPLETED)

        body = (await client.get(f"/api/missions/{mission_id}/events/stream")).text

    assert body.count("event: ") == len(mission.events)
    assert f"event: {EventType.MISSION_COMPLETED.value}" in body


async def test_missions_are_listed_newest_first(api):
    client, app = api()
    async with client:
        first = (await client.post("/api/missions", json={"goal": scenarios.GOAL})).json()["id"]
        approval = await _await_pending_approval(app, first)
        await client.post(f"/api/approvals/{approval.id}", json={"approved": True})
        await _await_status(app, first, MissionStatus.COMPLETED)

        listed = (await client.get("/api/missions")).json()
        assert [m["id"] for m in listed] == [first]
        assert listed[0]["task_count"] == 3


async def test_health_reports_configuration(api):
    client, _ = api()
    async with client:
        body = (await client.get("/api/health")).json()
    assert body["status"] == "ok"
    assert body["auto_approve_max_risk"] == "MEDIUM"
    assert EventType.MISSION_COMPLETED.value in body["event_types"]
