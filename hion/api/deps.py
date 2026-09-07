"""Application wiring.

One container holds the store, bus, approvals and engine so tests can build an
app with a different model factory without touching route code.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from hion.config import Settings, get_settings
from hion.events.bus import EventBus
from hion.llm.provider import ModelFactory, build_model
from hion.orchestration.approvals import ApprovalRegistry
from hion.orchestration.engine import MissionEngine
from hion.store.memory import InMemoryMissionStore, MissionStore


@dataclass(slots=True)
class Container:
    """Everything the API needs, constructed once per application."""

    settings: Settings
    store: MissionStore
    bus: EventBus
    approvals: ApprovalRegistry
    engine: MissionEngine


def build_container(
    settings: Settings | None = None,
    model_factory: ModelFactory | None = None,
) -> Container:
    """Assemble the application graph.

    The model is built lazily, once, on first use: importing the app must not
    require credentials, but every agent in a process should share one client.
    """
    settings = settings or get_settings()
    store = InMemoryMissionStore()
    bus = EventBus()
    approvals = ApprovalRegistry()

    if model_factory is None:
        model_factory = _lazy_singleton(lambda: build_model(settings))

    engine = MissionEngine(
        settings=settings,
        store=store,
        bus=bus,
        approvals=approvals,
        model_factory=model_factory,
    )
    return Container(settings=settings, store=store, bus=bus, approvals=approvals, engine=engine)


def _lazy_singleton(factory):
    cache: list = []

    def get():
        if not cache:
            cache.append(factory())
        return cache[0]

    return get


def container_of(request: Request) -> Container:
    """FastAPI dependency: the container attached to the running app."""
    return request.app.state.container
