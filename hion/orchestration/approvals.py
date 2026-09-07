"""Human-in-the-loop approvals.

A mission that needs sign-off genuinely suspends: the asyncio task awaits a
future that only an HTTP call (or the CLI) can resolve. Nothing proceeds on a
guess about what the human would have said.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from hion.domain.models import ApprovalRequest
from hion.errors import ApprovalNotFound

logger = logging.getLogger(__name__)


class ApprovalRegistry:
    """Tracks pending approval requests and their resolution."""

    def __init__(self) -> None:
        self._waiters: dict[str, asyncio.Future[bool]] = {}
        self._requests: dict[str, ApprovalRequest] = {}

    def open(self, request: ApprovalRequest) -> asyncio.Future[bool]:
        """Register a pending approval and return the future to await."""
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._waiters[request.id] = future
        self._requests[request.id] = request
        return future

    def resolve(
        self, approval_id: str, *, approved: bool, decided_by: str, note: str | None
    ) -> ApprovalRequest:
        """Record a human decision and wake the suspended mission.

        Raises:
            ApprovalNotFound: unknown id, or the request was already decided.
        """
        request = self._requests.get(approval_id)
        if request is None:
            raise ApprovalNotFound(f"No approval request with id {approval_id!r}")
        if request.status != "PENDING":
            raise ApprovalNotFound(f"Approval {approval_id!r} was already {request.status}")

        request.status = "GRANTED" if approved else "REJECTED"
        request.resolved_at = datetime.now(UTC)
        request.decided_by = decided_by
        request.note = note

        future = self._waiters.pop(approval_id, None)
        if future is not None and not future.done():
            future.set_result(approved)
        return request

    def expire(self, approval_id: str) -> None:
        """Mark an approval as timed out and drop its waiter."""
        request = self._requests.get(approval_id)
        if request is not None and request.status == "PENDING":
            request.status = "TIMED_OUT"
            request.resolved_at = datetime.now(UTC)
        self._waiters.pop(approval_id, None)

    def pending(self) -> list[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status == "PENDING"]

    def get(self, approval_id: str) -> ApprovalRequest | None:
        return self._requests.get(approval_id)
