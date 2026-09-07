"""Local-only backend for frontend development, with no model credentials.

This runs the real Hion FastAPI app - real engine, real event bus, real SSE
stream, real approval endpoint - with only the model provider swapped for the
same scripted test double the backend's own test suite uses
(tests/support/scripted_model.py). It exists so the frontend (web/) can be
built and demoed without a working Bedrock/Anthropic/OpenAI credential.

This is NOT a mock agent system and must never be presented as the product:
it is exactly the harness `tests/test_api.py` already validates against,
pointed at a live port instead of an httpx test client. The real path is
`hion serve` against a real provider (see `hion doctor` / `hion verify`).

Usage:
    python scripts/dev_backend.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from hion.api.app import create_app
from hion.config import Settings
from tests.support import scenarios
from tests.support.scripted_model import ScriptedModel


def main() -> None:
    settings = Settings(
        _env_file=None,
        model_provider="bedrock",
        model_id="scripted-dev-model",
        workspace_dir=Path("./workspace"),
        search_provider="none",
    )
    app = create_app(settings=settings, model_factory=lambda: ScriptedModel(scenarios.reference_script()))
    print("Scripted dev backend on http://localhost:8000 (frontend development only, not a real model).")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
