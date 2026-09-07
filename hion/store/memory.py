"""Mission persistence.

An in-memory store is the right call for the hackathon: missions are long-lived
inside one process and the API only ever reads them back. The
:class:`MissionStore` protocol keeps a database swap a one-file change.
"""

from __future__ import annotations

from typing import Protocol

from hion.domain.models import Mission
from hion.errors import MissionNotFound


class MissionStore(Protocol):
    """Storage contract for missions."""

    def add(self, mission: Mission) -> None: ...

    def get(self, mission_id: str) -> Mission: ...

    def find(self, mission_id: str) -> Mission | None: ...

    def list(self, limit: int = 50) -> list[Mission]: ...


class InMemoryMissionStore:
    """Dict-backed mission store."""

    def __init__(self) -> None:
        self._missions: dict[str, Mission] = {}

    def add(self, mission: Mission) -> None:
        self._missions[mission.id] = mission

    def get(self, mission_id: str) -> Mission:
        mission = self._missions.get(mission_id)
        if mission is None:
            raise MissionNotFound(f"No mission with id {mission_id!r}")
        return mission

    def find(self, mission_id: str) -> Mission | None:
        return self._missions.get(mission_id)

    def list(self, limit: int = 50) -> list[Mission]:
        missions = sorted(self._missions.values(), key=lambda m: m.created_at, reverse=True)
        return missions[:limit]
