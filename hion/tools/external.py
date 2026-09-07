"""HIGH-risk tools that reach outside Hion.

There is exactly one rule here: if the side effect cannot actually be performed,
the tool fails loudly. It never reports success for something that did not
happen. Reaching these tools at all requires clearing the Guardian gate.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from strands import tool
from strands.tools.decorator import DecoratedFunctionTool

from hion.tools.context import ExecutionContext

logger = logging.getLogger(__name__)


def build_external_tools(ctx: ExecutionContext) -> list[DecoratedFunctionTool]:
    """Create the external-side-effect toolset for a mission."""
    settings = ctx.settings

    @tool
    async def publish_external(channel: str, subject: str, body: str) -> dict[str, Any]:
        """Send a finished artifact outside Hion, to a real external destination.

        This is a HIGH-risk, irreversible action and requires human approval.

        Args:
            channel: Logical destination label, e.g. "webhook" or "stakeholders".
            subject: Short subject line describing what is being sent.
            body: The full content being published.
        """
        if not settings.external_webhook_url:
            return {
                "status": "error",
                "error": (
                    "No external destination is configured (HION_EXTERNAL_WEBHOOK_URL is unset), "
                    "so nothing was published. Report this instead of claiming delivery."
                ),
            }
        try:
            async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
                response = await client.post(
                    settings.external_webhook_url,
                    json={
                        "mission_id": ctx.mission_id,
                        "channel": channel,
                        "subject": subject,
                        "body": body,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("publish_external failed: %s", exc)
            return {"status": "error", "error": f"Delivery failed, nothing was published: {exc}"}

        return {
            "status": "ok",
            "channel": channel,
            "destination": settings.external_webhook_url,
            "http_status": response.status_code,
        }

    return [publish_external]
