from unittest.mock import Mock, patch
import requests
import pytest
from backend.services.research_service import ResearchServiceError, search_web

def test_search_skips_when_tavily_key_missing(monkeypatch):
    from backend.config import get_settings
    monkeypatch.setattr(get_settings(), "tavily_api_key", "")
    context, sources = search_web("current weather")
    assert context == ""
    assert sources == []

def test_search_returns_evidence_and_source(monkeypatch):
    from backend.config import get_settings
    monkeypatch.setattr(get_settings(), "tavily_api_key", "test-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"results": [{"title": "Example", "url": "https://example.com", "content": "Evidence"}]}
    with patch("backend.services.research_service.requests.post", return_value=response) as post:
        context, sources = search_web("question")
    assert "Evidence" in context
    assert len(sources) == 1
    assert sources[0].url == "https://example.com"
    assert post.call_args.kwargs["json"]["api_key"] == "test-key"

def test_search_converts_network_failure(monkeypatch):
    from backend.config import get_settings
    monkeypatch.setattr(get_settings(), "tavily_api_key", "test-key")
    with patch("backend.services.research_service.requests.post", side_effect=requests.Timeout("timeout")):
        with pytest.raises(ResearchServiceError):
            search_web("question")
