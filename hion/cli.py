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
from hion.errors import ConfigurationError
from hion.llm.preflight import check_provider
from hion.llm.provider import build_model
from hion.verify import REFERENCE_GOAL, run_verification


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

    sub.add_parser("doctor", help="Check that the configured model provider actually works.")

    verify = sub.add_parser(
        "verify", help="Run the reference mission against a real model and check the lifecycle."
    )
    verify.add_argument("--goal", default=REFERENCE_GOAL, help="Override the mission goal.")
    verify.add_argument("--verbose", "-v", action="store_true", help="Show debug logging.")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    if args.command == "serve":
        import uvicorn

        uvicorn.run("hion.asgi:app", host=args.host, port=args.port, reload=args.reload)
        return 0

    if args.command == "doctor":
        return asyncio.run(_doctor())

    if args.command == "verify":
        return asyncio.run(_verify(args.goal))

    return asyncio.run(_run_mission(args.goal))


async def _doctor() -> int:
    """Report whether Hion can actually reach a model, and how it is configured."""
    settings = get_settings()
    print("Hion configuration check\n" + "-" * 40)
    try:
        provider = settings.resolve_provider()
        model_id = settings.resolve_model_id(provider)
    except ConfigurationError as exc:
        print(f"provider   : NOT CONFIGURED\n\n{exc}")
        return 1

    print(f"provider   : {provider}")
    print(f"model      : {model_id}")
    print(f"workspace  : {settings.workspace_dir}")
    print(f"search     : {settings.search_provider}")
    print(f"revisions  : max {settings.max_revisions}, then {settings.on_revisions_exhausted}")
    print(f"auto-approve up to: {settings.auto_approve_max_risk.value} (HIGH always needs a human)")
    print("-" * 40)

    try:
        model = build_model(settings)
    except ConfigurationError as exc:
        print(f"provider   : UNUSABLE\n\n{exc}")
        return 1

    print("Calling the provider...", flush=True)
    status = await check_provider(model, settings)
    print(f"\nprovider   : {'REACHABLE' if status.reachable else 'UNREACHABLE'}")
    print(status.detail)
    return 0 if status.reachable else 1


async def _verify(goal: str) -> int:
    """Run the reference mission for real and print the lifecycle report."""
    settings = get_settings()
    try:
        model = build_model(settings)
    except ConfigurationError as exc:
        print(f"Cannot verify: {exc}", file=sys.stderr)
        return 1

    status = await check_provider(model, settings)
    if not status.reachable:
        print(f"Cannot verify: {status.detail}", file=sys.stderr)
        return 1

    print(f"Provider {status.provider} / {status.model_id} is reachable.")
    print(f"Running the reference mission for real:\n  {goal}\n")

    container = build_container(settings=settings)
    mission, checks = await run_verification(container, goal)

    print("\n" + "=" * 72)
    print("LIFECYCLE VERIFICATION")
    print("=" * 72)
    failures = 0
    for check in checks:
        if check.passed:
            mark = "PASS"
        elif check.required:
            mark = "FAIL"
            failures += 1
        else:
            mark = "WARN"
        print(f"[{mark}] {check.name}\n       {check.detail}")

    print("=" * 72)
    print(f"MISSION: {mission.id}  STATUS: {mission.status.value}")
    if mission.final_result:
        print("\n--- FINAL RESULT ---\n" + mission.final_result)
    if mission.error:
        print(f"\nERROR: {mission.error}", file=sys.stderr)
    print("\nREAL MODEL: " + ("PASS" if failures == 0 else "FAIL"))
    return 0 if failures == 0 else 1


async def _run_mission(goal: str) -> int:
    settings = get_settings()
    try:
        status = await check_provider(build_model(settings), settings)
    except ConfigurationError as exc:
        print(f"Cannot start: {exc}", file=sys.stderr)
        return 1
    if not status.reachable:
        print(f"Cannot start: {status.detail}", file=sys.stderr)
        return 1

    container = build_container(settings=settings)
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
