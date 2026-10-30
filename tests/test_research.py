from unittest.mock import Mock, patch

import pytest
import requests

from backend.services.research_service import ResearchServiceError, search_web


def _response(data):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = data
    return response


def test_search_skips_when_tavily_key_missing(monkeypatch):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "tavily_api_key", "")
    context, sources = search_web("current weather")
    assert context == ""
    assert sources == []


def test_search_returns_extracted_evidence_and_source(monkeypatch):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "tavily_api_key", "test-key")
    search = _response({
        "results": [{
            "title": "Example",
            "url": "https://example.com",
            "content": "Search snippet",
        }]
    })
    extract = _response({
        "results": [{
            "url": "https://example.com",
            "raw_content": "Full extracted page text",
        }],
        "failed_results": [],
    })
    with patch(
        "backend.services.research_service.requests.post",
        side_effect=[search, extract],
    ) as post:
        context, sources = search_web("question")

    assert "Full extracted page text" in context
    assert "Search snippet" not in context
    assert len(sources) == 1
    assert sources[0].url == "https://example.com"
    assert sources[0].snippet == "Full extracted page text"
    assert post.call_args_list[0].args[0].endswith("/search")
    assert post.call_args_list[1].args[0].endswith("/extract")
    assert post.call_args_list[1].kwargs["json"]["urls"] == ["https://example.com"]


def test_extract_failure_falls_back_to_search_snippet(monkeypatch):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "tavily_api_key", "test-key")
    search = _response({
        "results": [{
            "title": "Example",
            "url": "https://example.com",
            "content": "Search snippet",
        }]
    })
    with patch(
        "backend.services.research_service.requests.post",
        side_effect=[search, requests.Timeout("timeout")],
    ):
        context, sources = search_web("question")

    assert "Search snippet" in context
    assert len(sources) == 1


def test_search_converts_search_network_failure(monkeypatch):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "tavily_api_key", "test-key")
    with patch(
        "backend.services.research_service.requests.post",
        side_effect=requests.Timeout("timeout"),
    ):
        with pytest.raises(ResearchServiceError):
            search_web("question")
