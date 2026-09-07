"""Provider connectivity checks and error translation.

A missing API key is caught by :mod:`hion.llm.provider` before anything runs.
Credentials that exist but do not work are a different problem: they surface deep
inside a mission as a botocore or SDK exception that means nothing to the person
running Hion. This module turns those into one actionable sentence, and offers a
cheap round-trip so the failure can be found before a mission starts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from strands import Agent
from strands.models.model import Model

from hion.config import Settings
from hion.errors import ProviderUnavailable

logger = logging.getLogger(__name__)

#: Substrings that identify an unusable credential, and what to do about it.
#: Matched against the exception text, so this works for every provider without
#: importing their optional SDKs.
_DIAGNOSES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "UnrecognizedClientException",
            "InvalidClientTokenId",
            "security token included in the request is invalid",
        ),
        "the credentials were rejected as invalid",
    ),
    (
        ("ExpiredToken", "ExpiredTokenException", "token has expired"),
        "the credentials have expired",
    ),
    (
        (
            "AuthenticationError",
            "authentication_error",
            "x-api-key header is required",
            "invalid_api_key",
            "401",
        ),
        "the API key was missing or rejected",
    ),
    (
        ("AccessDeniedException", "PermissionDenied", "not authorized", "403"),
        "the credentials are valid but not authorised for this model",
    ),
    (
        ("ResourceNotFoundException", "NotFoundError", "could not find model", "model not found"),
        "the model id does not exist for this account or region",
    ),
    (
        ("ValidationException", "on-demand throughput isn", "invocation of model ID"),
        "the model id is not usable this way in this region (it may need an inference profile)",
    ),
    (
        (
            "EndpointConnectionError",
            "ConnectError",
            "Connection refused",
            "Name or service not known",
            "getaddrinfo",
        ),
        "the provider endpoint could not be reached from this network",
    ),
    (
        ("ThrottlingException", "RateLimit", "429"),
        "the provider is rate limiting this account",
    ),
)

#: What to set, per provider, when the credential is the problem.
_REMEDIES: dict[str, str] = {
    "bedrock": (
        "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (or AWS_PROFILE) for an account with "
        "Bedrock access, set HION_AWS_REGION to a region where HION_MODEL_ID is enabled, and "
        "enable that model in the Bedrock console under Model access."
    ),
    "anthropic": "Set HION_MODEL_API_KEY to an Anthropic API key from https://console.anthropic.com/settings/keys",
    "openai": "Set HION_MODEL_API_KEY to an OpenAI API key from https://platform.openai.com/api-keys",
    "ollama": "Start Ollama locally and set HION_MODEL_BASE_URL (default http://localhost:11434).",
}


@dataclass(frozen=True)
class ProviderStatus:
    """The outcome of a provider connectivity check."""

    provider: str
    model_id: str
    reachable: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "reachable": self.reachable,
            "detail": self.detail,
        }


def diagnose(exc: BaseException, settings: Settings) -> str | None:
    """Translate a provider exception into an actionable message.

    Returns:
        A one-paragraph explanation, or ``None`` if this does not look like a
        provider configuration problem.
    """
    text = f"{type(exc).__name__}: {exc}"
    provider: str
    model_id: str
    try:
        provider = settings.resolve_provider()
        model_id = settings.resolve_model_id(provider)
    except Exception:  # noqa: BLE001 - diagnosis must never raise on top of a failure
        provider, model_id = settings.model_provider, settings.model_id or "(unset)"

    for markers, cause in _DIAGNOSES:
        if any(marker in text for marker in markers):
            remedy = _REMEDIES.get(provider, "Check HION_MODEL_PROVIDER and its credentials.")
            return (
                f"Model provider {provider!r} (model {model_id!r}) is not usable: {cause}. {remedy}"
            )
    return None


async def check_provider(model: Model, settings: Settings) -> ProviderStatus:
    """Make one cheap real call to confirm the provider actually answers."""
    try:
        provider = settings.resolve_provider()
        model_id = settings.resolve_model_id(provider)
    except Exception as exc:  # noqa: BLE001 - nothing configured is itself a status
        return ProviderStatus(settings.model_provider, settings.model_id or "(unset)", False, str(exc))

    try:
        agent = Agent(
            model=model,
            system_prompt="Reply with the single word OK.",
            callback_handler=None,
        )
        await agent.invoke_async("ping")
    except Exception as exc:  # noqa: BLE001 - every failure mode is reported, not raised
        detail = diagnose(exc, settings) or f"{type(exc).__name__}: {exc}"
        logger.warning("Provider check failed: %s", detail)
        return ProviderStatus(provider, model_id, False, detail)
    return ProviderStatus(provider, model_id, True, "Provider answered a test prompt.")


async def require_provider(model: Model, settings: Settings) -> ProviderStatus:
    """Confirm the provider works, or refuse to start.

    Raises:
        ProviderUnavailable: the provider could not be reached or authenticated.
    """
    status = await check_provider(model, settings)
    if not status.reachable:
        raise ProviderUnavailable(status.detail)
    return status
