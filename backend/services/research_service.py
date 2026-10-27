"""Tavily search integration for Mnemos."""
from __future__ import annotations

import logging
from typing import Any

import requests

from backend.config import get_settings
from backend.schemas import ResearchSource

logger = logging.getLogger("mnemos.research_service")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class ResearchServiceError(RuntimeError):
    """Raised when Tavily is configured but its request fails."""


def tavily_configured() -> bool:
    return bool(get_settings().tavily_api_key.strip())


def search_web(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "basic",
    timeout: float = 15.0,
) -> tuple[str, list[ResearchSource]]:
    """Search current web information and return evidence plus source metadata.

    If no Tavily key is configured, return empty context/sources so the agent can
    gracefully continue with model-only answering. Upstream errors are logged and
    converted into ResearchServiceError for the agent to handle.
    """
    settings = get_settings()
    api_key = settings.tavily_api_key.strip()
    if not api_key:
        return "", []

    normalized_query = query.strip()
    if not normalized_query:
        return "", []
    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": normalized_query[:2000],
        "search_depth": search_depth if search_depth in {"basic", "advanced"} else "basic",
        "max_results": max(1, min(int(max_results), 10)),
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        response = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.exception("Tavily search request failed")
        raise ResearchServiceError(
            "Tavily search failed. Check the API key, quota, network, and service status."
        ) from exc

    results = data.get("results", [])
    if not isinstance(results, list):
        results = []

    evidence: list[str] = []
    sources: list[ResearchSource] = []
    for item in results[:payload["max_results"]]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            continue
        title = str(item.get("title") or url)[:500]
        snippet = str(item.get("content") or item.get("snippet") or "")[:4000]
        score = item.get("score")
        score_label = f" (relevance {score:.2f})" if isinstance(score, (int, float)) else ""
        evidence.append(f"Title: {title}\nURL: {url}{score_label}\nEvidence: {snippet}")
        sources.append(ResearchSource(title=title, url=url, snippet=snippet or None))

    return "\n\n".join(evidence), sources
