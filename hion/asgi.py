"""ASGI entrypoint: ``uvicorn hion.asgi:app``.

Model construction is lazy, so importing this module does not require provider
credentials - they are only needed once a mission actually starts.
"""

from __future__ import annotations

from hion.api.app import create_app

app = create_app()
