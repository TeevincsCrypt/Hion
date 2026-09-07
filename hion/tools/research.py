"""Real web research tools.

If no search backend is configured these tools return an explicit error. They
never invent results - a research agent that cannot search must say so, and the
Critic will catch a brief built on nothing.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any

import httpx
from strands import tool
from strands.tools.decorator import DecoratedFunctionTool

from hion.tools.context import ExecutionContext

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_STRIP_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")
_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>'
    r'.*?<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    re.DOTALL,
)


def _clean(fragment: str) -> str:
    return html.unescape(_STRIP_RE.sub("", fragment)).strip()


def build_research_tools(ctx: ExecutionContext) -> list[DecoratedFunctionTool]:
    """Create the research toolset for a mission."""
    settings = ctx.settings

    async def _search_tavily(query: str, max_results: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                    "include_answer": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "score": item.get("score"),
            }
            for item in payload.get("results", [])
        ]
        return {
            "status": "ok",
            "provider": "tavily",
            "query": query,
            "answer": payload.get("answer"),
            "results": results,
        }

    async def _search_duckduckgo(query: str, max_results: int) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HionResearchAgent/0.1)"},
        ) as client:
            response = await client.post(
                "https://html.duckduckgo.com/html/", data={"q": query}
            )
            response.raise_for_status()
            body = response.text
        results = [
            {
                "title": _clean(match.group("title")),
                "url": html.unescape(match.group("url")),
                "snippet": _clean(match.group("snippet")),
            }
            for match in _DDG_RESULT_RE.finditer(body)
        ][:max_results]
        if not results:
            return {
                "status": "error",
                "provider": "duckduckgo",
                "error": "No parseable results returned. Try a different query or fetch a known URL.",
            }
        return {"status": "ok", "provider": "duckduckgo", "query": query, "results": results}

    @tool
    async def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
        """Search the public web and return ranked results with snippets and URLs.

        Always cite the returned URLs in your output. If this tool reports an
        error, say so plainly instead of guessing at facts.

        Args:
            query: A focused search query.
            max_results: How many results to return (1-10).
        """
        max_results = max(1, min(int(max_results), 10))
        provider = settings.search_provider
        if provider == "none":
            return {
                "status": "error",
                "error": "No web search backend is configured (HION_SEARCH_PROVIDER=none).",
            }
        if provider == "auto":
            provider = "tavily" if settings.tavily_api_key else "duckduckgo"
        if provider == "tavily" and not settings.tavily_api_key:
            return {"status": "error", "error": "HION_TAVILY_API_KEY is not set."}

        try:
            if provider == "tavily":
                return await _search_tavily(query, max_results)
            return await _search_duckduckgo(query, max_results)
        except httpx.HTTPError as exc:
            logger.warning("web_search failed: %s", exc)
            return {"status": "error", "provider": provider, "error": f"Search request failed: {exc}"}

    @tool
    async def fetch_url(url: str) -> dict[str, Any]:
        """Fetch a web page and return its readable text.

        Use this to verify a claim against the actual source after web_search.

        Args:
            url: Absolute http(s) URL to fetch.
        """
        if not url.startswith(("http://", "https://")):
            return {"status": "error", "error": "Only http:// and https:// URLs can be fetched."}
        try:
            async with httpx.AsyncClient(
                timeout=settings.http_timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; HionResearchAgent/0.1)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                body = response.text
        except httpx.HTTPError as exc:
            logger.warning("fetch_url failed for %s: %s", url, exc)
            return {"status": "error", "url": url, "error": f"Fetch failed: {exc}"}

        text = _WS_RE.sub("\n\n", _clean(_TAG_RE.sub(" ", body)))
        return {
            "status": "ok",
            "url": url,
            "content": text[: settings.max_fetch_chars],
            "truncated": len(text) > settings.max_fetch_chars,
        }

    return [web_search, fetch_url]
