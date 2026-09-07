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

ModelProvider = Literal["bedrock", "anthropic", "openai", "ollama"]
SearchProvider = Literal["auto", "tavily", "duckduckgo", "none"]


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
    model_provider: ModelProvider = "bedrock"
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    model_api_key: str | None = None
    model_base_url: str | None = None
    aws_region: str = "us-west-2"
    max_tokens: int = 8192
    temperature: float = 0.3

    # -- Orchestration -----------------------------------------------------
    max_revisions: int = Field(default=2, ge=0, le=5)
    max_concurrency: int = Field(default=3, ge=1, le=10)
    auto_approve_max_risk: RiskLevel = RiskLevel.MEDIUM
    on_revisions_exhausted: Literal["accept", "fail"] = "accept"
    approval_timeout_seconds: int = Field(default=900, ge=1)

    # -- Tools -------------------------------------------------------------
    workspace_dir: Path = Path("./workspace")
    search_provider: SearchProvider = "auto"
    tavily_api_key: str | None = None
    http_timeout_seconds: float = 20.0
    max_search_results: int = 6
    max_fetch_chars: int = 12_000
    external_webhook_url: str | None = None

    def mission_workspace(self, mission_id: str) -> Path:
        """Filesystem sandbox root for a single mission."""
        return (self.workspace_dir / mission_id).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton."""
    return Settings()
