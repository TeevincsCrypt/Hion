"""Model provider wiring."""

from __future__ import annotations

import pytest
from strands.models.model import Model

from hion.errors import ConfigurationError
from hion.llm.provider import build_model


def test_bedrock_is_the_default_and_needs_no_extras(settings):
    model = build_model(settings)
    assert isinstance(model, Model)
    assert model.get_config()["model_id"] == settings.model_id


@pytest.mark.parametrize("provider", ["anthropic", "openai", "ollama"])
def test_optional_providers_fail_with_an_actionable_message(settings, provider):
    """Whichever is missing - the extra or the key - the error says how to fix it."""
    with pytest.raises(ConfigurationError, match=r"(HION_MODEL_API_KEY|pip install)"):
        build_model(settings.model_copy(update={"model_provider": provider}))


def test_an_unknown_provider_is_rejected(settings):
    broken = settings.model_copy(update={"model_provider": "definitely-not-a-provider"})
    with pytest.raises(ConfigurationError, match="Unknown HION_MODEL_PROVIDER"):
        build_model(broken)
