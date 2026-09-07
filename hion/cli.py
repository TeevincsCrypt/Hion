"""Command line entrypoints for Hion.

``hion serve``   - run the HTTP API.
``hion run GOAL`` - run one mission in the terminal with a live event feed.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from hion.api.deps import build_container
from hion.config import get_settings
from hion.domain.enums import EventType, MissionStatus
from hion.domain.models import MissionEvent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hion", description="Hion autonomous work management.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the Hion HTTP API.")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    run = sub.add_parser("run", help="Run a single mission and print the result.")
    run.add_argument("goal", help="The goal to hand to Hion.")
    run.add_argument("--verbose", "-v", action="store_true", help="Show debug logging.")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    if args.command == "serve":
        import uvicorn

        uvicorn.run("hion.asgi:app", host=args.host, port=args.port, reload=args.reload)
        return 0

    return asyncio.run(_run_mission(args.goal))


async def _run_mission(goal: str) -> int:
    container = build_container(settings=get_settings())
    mission = await container.engine.start_mission(goal)
    print(f"Mission {mission.id}\nGoal: {goal}\n", flush=True)

    async def follow() -> None:
        async with container.bus.subscription(mission.id) as queue:
            while not (mission.is_terminal and queue.empty()):
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                except TimeoutError:
                    continue
                _print_event(event)

    follower = asyncio.create_task(follow())
    await container.engine.wait_for(mission.id)
    await asyncio.wait_for(follower, timeout=5.0)

    print("\n" + "=" * 72)
    print(f"STATUS: {mission.status.value}")
    print("=" * 72)
    if mission.final_result:
        print(mission.final_result)
    elif mission.error:
        print(mission.error, file=sys.stderr)
    return 0 if mission.status is MissionStatus.COMPLETED else 1


_ICONS = {
    EventType.APPROVAL_REQUIRED: "!!",
    EventType.REVISION_REQUESTED: "<<",
    EventType.TOOL_BLOCKED: "XX",
    EventType.MISSION_FAILED: "XX",
    EventType.TASK_FAILED: "XX",
    EventType.MISSION_COMPLETED: "**",
}


def _print_event(event: MissionEvent) -> None:
    icon = _ICONS.get(event.type, "..")
    agent = f"[{event.agent.value}]" if event.agent else ""
    print(f"{icon} {event.type.value:<22} {agent:<12} {event.message}", flush=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
