"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hion.api.deps import build_container
from hion.api.routes import router
from hion.config import Settings
from hion.llm.provider import ModelFactory

logger = logging.getLogger(__name__)

DESCRIPTION = """\
Hion is an autonomous work management system built on the Strands Agents SDK.

Give it a goal. A Commander agent plans the work, delegates each task to a
specialist (research, analyst, creator), a Critic evaluates every result and
sends weak work back for revision, and a Guardian decides what a human has to
approve before it happens. Every transition is recorded as a mission event and
streamed live.
"""


def create_app(
    settings: Settings | None = None,
    model_factory: ModelFactory | None = None,
) -> FastAPI:
    """Build the Hion API.

    Args:
        settings: Overrides the environment-derived configuration.
        model_factory: Supplies the Strands model. Tests inject their own.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    app = FastAPI(title="Hion", version="0.1.0", description=DESCRIPTION)
    app.state.container = build_container(settings=settings, model_factory=model_factory)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": "hion", "docs": "/docs", "missions": "/api/missions"}

    return app

