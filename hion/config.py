"""Runtime configuration for Hion.

Everything is environment-driven with a ``HION_`` prefix so the same code runs
locally, in CI (with the scripted test model) and against a real provider.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from hion.domain.enums import RiskLevel
from hion.errors import ConfigurationError

ModelProvider = Literal["auto", "bedrock", "anthropic", "openai", "ollama"]
ConcreteProvider = Literal["bedrock", "anthropic", "openai", "ollama"]
SearchProvider = Literal["auto", "tavily", "duckduckgo", "none"]

#: Default model per provider, used when HION_MODEL_ID is not set. Model ids are
#: not portable between providers, so there cannot be one global default.
DEFAULT_MODEL_IDS: dict[str, str] = {
    "bedrock": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai": "gpt-4o",
    "ollama": "llama3.1",
}


class Settings(BaseSettings):
    """Hion configuration."""

    model_config = SettingsConfigDict(
        env_prefix="HION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # -- Model provider ----------------------------------------------------
    #: "auto" prefers Bedrock when the environment already has AWS credentials,
    #: and falls back to an API-key provider. Set it explicitly to pin one.
    model_provider: ModelProvider = "auto"
    #: Left unset, each provider uses its own default from DEFAULT_MODEL_IDS.
    model_id: str | None = None
    model_api_key: str | None = None
    model_base_url: str | None = None
    aws_region: str = "us-west-2"
    max_tokens: int = 8192
    temperature: float = 0.3

    # -- Orchestration -----------------------------------------------------
    max_revisions: int = Field(default=2, ge=0, le=5)
    max_concurrency: int = Field(default=3, ge=1, le=10)
    auto_approve_max_risk: RiskLevel = RiskLevel.MEDIUM
    #: What to do when the Critic still rejects after max_revisions. Failing is
    #: the default: shipping work a critic rejected is worse than reporting that
    #: it could not be brought up to standard.
    on_revisions_exhausted: Literal["fail", "accept"] = "fail"
    approval_timeout_seconds: int = Field(default=900, ge=1)

    # -- Critic calibration ------------------------------------------------
    #: Overall score below which an "approved" verdict is overridden to a rejection.
    critic_approval_threshold: int = Field(default=75, ge=0, le=100)
    #: Any single dimension below this also blocks approval, so a result cannot
    #: be waved through on a strong average while one axis is failing.
    critic_min_dimension_score: int = Field(default=60, ge=0, le=100)

    # -- Tools -------------------------------------------------------------
    workspace_dir: Path = Path("./workspace")
    search_provider: SearchProvider = "auto"
    tavily_api_key: str | None = None
    http_timeout_seconds: float = 20.0
    max_search_results: int = 6
    max_fetch_chars: int = 12_000
    external_webhook_url: str | None = None

    def resolve_provider(self) -> ConcreteProvider:
        """Pick the provider to use, resolving "auto" against the environment.

        Selection is static and cheap: it checks whether credentials are *present*,
        not whether they work. ``hion doctor`` makes the real call.

        Raises:
            ConfigurationError: nothing usable is configured.
        """
        if self.model_provider != "auto":
            return self.model_provider
        if _has_aws_credentials():
            return "bedrock"
        if self.model_api_key:
            return "anthropic"
        raise ConfigurationError(
            "No model provider is configured. Either provide AWS credentials for Amazon "
            "Bedrock (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, or AWS_PROFILE), or set "
            "HION_MODEL_API_KEY for an API-key provider and HION_MODEL_PROVIDER to "
            "'anthropic' or 'openai'. See .env.example."
        )

    def resolve_model_id(self, provider: str | None = None) -> str:
        """The model id to use, defaulting per provider."""
        provider = provider or self.resolve_provider()
        return self.model_id or DEFAULT_MODEL_IDS[provider]

    def mission_workspace(self, mission_id: str) -> Path:
        """Filesystem sandbox root for a single mission."""
        return (self.workspace_dir / mission_id).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton."""
    return Settings()


def _has_aws_credentials() -> bool:
    """Whether boto3 can resolve credentials from anywhere in the environment."""
    try:
        import boto3

        return boto3.Session().get_credentials() is not None
    except Exception:  # noqa: BLE001 - absence of credentials must never crash startup
        return False
