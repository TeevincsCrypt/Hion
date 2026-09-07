"""Hion exception hierarchy."""

from __future__ import annotations


class HionError(Exception):
    """Base class for all Hion errors."""


class ConfigurationError(HionError):
    """Hion is missing configuration it needs to run."""


class PlanningError(HionError):
    """The Commander could not produce a usable plan."""


class ApprovalRejected(HionError):
    """A human rejected a required approval."""


class ApprovalTimeout(HionError):
    """A required approval was not answered in time."""


class MissionNotFound(HionError):
    """No mission with the requested id."""


class ApprovalNotFound(HionError):
    """No approval request with the requested id."""


class ToolBlocked(HionError):
    """The Guardian refused to let a tool call execute."""


class ProviderUnavailable(ConfigurationError):
    """A model provider is configured but cannot actually be reached."""


class MalformedModelOutput(HionError):
    """An agent finished without producing the structured output it was asked for."""
