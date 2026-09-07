"""Builds the Strands ``Model`` that every Hion agent runs on.

Hion is provider-agnostic on purpose: the orchestration engine only ever sees a
``strands.models.model.Model``. Swapping Bedrock for Anthropic, OpenAI or a local
Ollama is a config change, and tests inject their own ``Model`` implementation.
"""

from __future__ import annotations

import logging
from typing import Protocol

from strands.models.model import Model

from hion.config import Settings
from hion.errors import ConfigurationError

logger = logging.getLogger(__name__)


class ModelFactory(Protocol):
    """Anything that can produce the model backing Hion's agents."""

    def __call__(self) -> Model: ...


def build_model(settings: Settings) -> Model:
    """Construct the configured Strands model provider.

    Raises:
        ConfigurationError: the provider is unknown, or its optional extra is
            not installed, or a required credential is missing.
    """
    provider = settings.model_provider
    builder = _BUILDERS.get(provider)
    if builder is None:
        raise ConfigurationError(
            f"Unknown HION_MODEL_PROVIDER {provider!r}. Expected one of {sorted(_BUILDERS)}."
        )
    logger.info("Building %s model %s", provider, settings.model_id)
    return builder(settings)


def _build_bedrock(settings: Settings) -> Model:
    from strands.models import BedrockModel

    return BedrockModel(
        model_id=settings.model_id,
        region_name=settings.aws_region,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )


def _build_anthropic(settings: Settings) -> Model:
    try:
        from strands.models.anthropic import AnthropicModel
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise ConfigurationError(
            "The Anthropic provider requires the 'anthropic' extra: pip install 'hion[anthropic]'"
        ) from exc

    if not settings.model_api_key:
        raise ConfigurationError("HION_MODEL_API_KEY is required when HION_MODEL_PROVIDER=anthropic")

    client_args: dict[str, object] = {"api_key": settings.model_api_key}
    if settings.model_base_url:
        client_args["base_url"] = settings.model_base_url
    return AnthropicModel(
        client_args=client_args,
        model_id=settings.model_id,
        max_tokens=settings.max_tokens,
        params={"temperature": settings.temperature},
    )


def _build_openai(settings: Settings) -> Model:
    try:
        from strands.models.openai import OpenAIModel
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise ConfigurationError(
            "The OpenAI provider requires the 'openai' extra: pip install 'hion[openai]'"
        ) from exc

    if not settings.model_api_key:
        raise ConfigurationError("HION_MODEL_API_KEY is required when HION_MODEL_PROVIDER=openai")

    client_args: dict[str, object] = {"api_key": settings.model_api_key}
    if settings.model_base_url:
        client_args["base_url"] = settings.model_base_url
    return OpenAIModel(
        client_args=client_args,
        model_id=settings.model_id,
        params={"temperature": settings.temperature, "max_tokens": settings.max_tokens},
    )


def _build_ollama(settings: Settings) -> Model:
    try:
        from strands.models.ollama import OllamaModel
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise ConfigurationError(
            "The Ollama provider requires the 'ollama' extra: pip install 'hion[ollama]'"
        ) from exc

    return OllamaModel(
        host=settings.model_base_url or "http://localhost:11434",
        model_id=settings.model_id,
        temperature=settings.temperature,
    )


_BUILDERS = {
    "bedrock": _build_bedrock,
    "anthropic": _build_anthropic,
    "openai": _build_openai,
    "ollama": _build_ollama,
}
