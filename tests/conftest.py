"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from hion.api.deps import Container, build_container
from hion.config import Settings
from hion.domain.enums import RiskLevel
from tests.support.scripted_model import ScriptedModel


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings isolated from the developer's environment and filesystem."""
    return Settings(
        _env_file=None,
        model_provider="bedrock",
        model_id="scripted-test-model",
        workspace_dir=tmp_path / "workspace",
        max_revisions=2,
        max_concurrency=3,
        auto_approve_max_risk=RiskLevel.MEDIUM,
        on_revisions_exhausted="accept",
        approval_timeout_seconds=10,
        search_provider="none",
        external_webhook_url=None,
    )


@pytest.fixture
def make_container(settings: Settings):
    """Build an application container backed by a scripted model."""

    def factory(script: dict[str, list], **overrides) -> tuple[Container, ScriptedModel]:
        effective = settings.model_copy(update=overrides) if overrides else settings
        model = ScriptedModel(script)
        container = build_container(settings=effective, model_factory=lambda: model)
        return container, model

    return factory
