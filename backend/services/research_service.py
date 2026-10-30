"""Tavily search and page extraction integration for Mnemos."""
from __future__ import annotations

import logging
from typing import Any

import requests

from backend.config import get_settings
from backend.schemas import ResearchSource

logger = logging.getLogger("mnemos.research_service")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


class ResearchServiceError(RuntimeError):
    """Raised when Tavily search fails."""


def tavily_configured() -> bool:
    return bool(get_settings().tavily_api_key.strip())


def search_web(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "basic",
    extract_depth: str = "basic",
    extract_limit: int = 3,
    timeout: float = 15.0,
) -> tuple[str, list[ResearchSource]]:
    """Search, then extract selected source pages and return grounded evidence.

    Search is the primary discovery step. The top extraction URLs are sent to
    Tavily Extract; snippets remain the fallback when pages cannot be extracted.
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

    valid: list[tuple[str, str, str, Any]] = []
    for item in results[:payload["max_results"]]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            continue
        title = str(item.get("title") or url)[:500]
        snippet = str(item.get("content") or item.get("snippet") or "")[:4000]
        valid.append((url, title, snippet, item.get("score")))

    extracted: dict[str, str] = {}
    safe_limit = max(0, min(int(extract_limit), 20))
    urls = [item[0] for item in valid[:safe_limit]]
    if urls:
        extract_payload = {
            "api_key": api_key,
            "urls": urls,
            "extract_depth": extract_depth if extract_depth in {"basic", "advanced"} else "basic",
            "format": "markdown",
            "include_images": False,
        }
        try:
            extract_response = requests.post(
                TAVILY_EXTRACT_URL,
                json=extract_payload,
                timeout=max(timeout, 30.0),
            )
            extract_response.raise_for_status()
            extract_data = extract_response.json()
            extracted_results = extract_data.get("results", [])
            if isinstance(extracted_results, list):
                for item in extracted_results:
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url")
                    content = item.get("raw_content") or item.get("content") or ""
                    if isinstance(url, str) and isinstance(content, str) and content.strip():
                        extracted[url] = content.strip()[:12000]
            failed_results = extract_data.get("failed_results", [])
            if failed_results:
                logger.info(
                    "Tavily Extract could not process %d selected URLs",
                    len(failed_results),
                )
        except (requests.RequestException, ValueError):
            logger.warning("Tavily extraction failed; using search snippets", exc_info=True)

    evidence: list[str] = []
    sources: list[ResearchSource] = []
    for url, title, snippet, score in valid:
        page_content = extracted.get(url) or snippet
        score_label = f" (relevance {score:.2f})" if isinstance(score, (int, float)) else ""
        evidence.append(f"Title: {title}\nURL: {url}{score_label}\nEvidence: {page_content}")
        sources.append(ResearchSource(title=title, url=url, snippet=page_content[:4000] or None))

    return "\n\n".join(evidence), sources
