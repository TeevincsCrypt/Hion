# Runs the real Hion FastAPI backend (hion.asgi:app) as a persistent process -
# required because missions run in-memory, background asyncio tasks, and the
# SSE event stream all need a long-lived server, which is why this cannot be
# deployed as a Vercel serverless function alongside the web/ frontend.
FROM python:3.11-slim

WORKDIR /app

# Which optional model-provider extra to install (anthropic | openai | ollama).
# Bedrock needs no extra - it ships with the base strands-agents dependency.
ARG EXTRAS=anthropic
ENV PYTHONUNBUFFERED=1 \
    HION_WORKSPACE_DIR=/app/workspace

COPY pyproject.toml README.md ./
COPY hion ./hion

RUN pip install --no-cache-dir ".[${EXTRAS}]" && mkdir -p /app/workspace

EXPOSE 8000
CMD ["sh", "-c", "uvicorn hion.asgi:app --host 0.0.0.0 --port ${PORT:-8000}"]
