from unittest.mock import AsyncMock, patch

from backend.schemas import ChatResponse


def test_chat_requires_authentication(client):
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 401


def test_chat_uses_authenticated_user_not_payload_user_id(client, account):
    auth, headers = account
    mocked = ChatResponse(answer="Hello.", model="test-model", conversation_id="conversation-test")
    fake_settings = type("Settings", (), {"has_nebius_key": True})()
    with (
        patch("backend.routers.chat.get_settings", return_value=fake_settings),
        patch("backend.routers.chat.handle_chat", new=AsyncMock(return_value=mocked)) as handle,
    ):
        response = client.post(
            "/chat",
            headers=headers,
            json={"message": "hello", "user_id": "someone-elses-account"},
        )
    assert response.status_code == 200, response.text
    assert handle.await_args.args[1].user_id == auth["user_id"]


def test_stream_route_returns_server_sent_events(client, account):
    import json
    from unittest.mock import AsyncMock, patch

    auth, headers = account
    async def fake_stream(_db, payload):
        yield {"type": "token", "token": "Hello", "model": "nano"}
        yield {"type": "done", "response": {
            "answer": "Hello", "model": "nano", "conversation_id": "thread-1",
            "research_sources": [], "memories_used": [],
        }}

    fake_settings = type("Settings", (), {"has_nebius_key": True})()
    with (
        patch("backend.routers.chat.get_settings", return_value=fake_settings),
        patch("backend.routers.chat.handle_chat_stream", side_effect=fake_stream),
    ):
        response = client.post("/chat/stream", headers=headers, json={"message": "hello"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "token"
    assert events[1]["type"] == "done"
    assert events[1]["response"]["model"] == "nano"
    assert auth["user_id"]


def test_automatic_memory_extraction_uses_sanitized_user_text_only(client, account):
    from unittest.mock import AsyncMock, patch

    _, headers = account
    fake_settings = type("Settings", (), {"has_nebius_key": True})()
    with (
        patch("backend.routers.chat.get_settings", return_value=fake_settings),
        patch("backend.services.agent_service.model_client.classify_research_need", new=AsyncMock(return_value=False)),
        patch("backend.services.agent_service.model_client.answer_with_model", new=AsyncMock(return_value=("The assistant response is not a memory source.", "super"))),
        patch("backend.services.agent_service.model_client.summarize_memory", new=AsyncMock(return_value="User prefers concise answers.")) as summarize,
    ):
        response = client.post("/chat", headers=headers, json={"message": "I prefer concise answers. Email me at alex@example.com."})

    assert response.status_code == 200, response.text
    summarized_text = summarize.await_args.args[0]
    assert "alex@example.com" not in summarized_text
    assert "[REDACTED_EMAIL]" in summarized_text
    assert "assistant response" not in summarized_text.lower()
    memories = client.get("/memories", headers=headers).json()["memories"]
    assert memories[0]["content"] == "User prefers concise answers."


def test_explicit_preference_is_saved_when_extractor_returns_no_memory(client, account):
    _, headers = account
    fake_settings = type("Settings", (), {"has_nebius_key": True})()
    prompt = "Please remember this stable preference: I prefer concise answers with a short summary first, followed by numbered steps when instructions are needed."
    with (
        patch("backend.routers.chat.get_settings", return_value=fake_settings),
        patch("backend.services.agent_service.model_client.classify_research_need", new=AsyncMock(return_value=False)),
        patch("backend.services.agent_service.model_client.answer_with_model", new=AsyncMock(return_value=("Understood.", "super"))),
        patch("backend.services.agent_service.model_client.summarize_memory", new=AsyncMock(return_value="NO_MEMORY")),
    ):
        response = client.post("/chat", headers=headers, json={"message": prompt})
    assert response.status_code == 200, response.text
    memories = client.get("/memories", headers=headers).json()["memories"]
    assert len(memories) == 1
    assert "I prefer concise answers" in memories[0]["content"]


def test_memory_extractor_unexpected_exception_does_not_break_chat_or_explicit_memory(client, account):
    _, headers = account
    fake_settings = type("Settings", (), {"has_nebius_key": True})()
    prompt = "Please remember that I prefer short answers."
    with (
        patch("backend.routers.chat.get_settings", return_value=fake_settings),
        patch("backend.services.agent_service.model_client.classify_research_need", new=AsyncMock(return_value=False)),
        patch("backend.services.agent_service.model_client.answer_with_model", new=AsyncMock(return_value=("Here is the answer.", "super"))),
        patch("backend.services.agent_service.model_client.summarize_memory", new=AsyncMock(side_effect=RuntimeError("unexpected extractor error"))),
    ):
        response = client.post("/chat", headers=headers, json={"message": prompt})
    assert response.status_code == 200, response.text
    assert response.json()["answer"] == "Here is the answer."
    memories = client.get("/memories", headers=headers).json()["memories"]
    assert len(memories) == 1
    assert "prefer short answers" in memories[0]["content"].lower()


def test_explicit_current_research_uses_tavily_and_requests_natural_answer(client, account):
    from backend.schemas import ResearchSource

    _, headers = account
    fake_settings = type("Settings", (), {"has_nebius_key": True})()
    prompt = "Search the web for the latest official announcement about NVIDIA Nemotron and include source links."
    with (
        patch("backend.routers.chat.get_settings", return_value=fake_settings),
        patch("backend.services.agent_service.tavily_configured", return_value=True),
        patch("backend.services.agent_service.search_web", return_value=("Title: Official source\\nEvidence: model announcement", [ResearchSource(title="Official source", url="https://example.com", snippet="model announcement")])) as search,
        patch("backend.services.agent_service.model_client.classify_research_need", new=AsyncMock(return_value=False)) as classify,
        patch("backend.services.agent_service.model_client.answer_with_model", new=AsyncMock(return_value=("The announcement confirms availability.", "super"))) as answer,
        patch("backend.services.agent_service.model_client.summarize_memory", new=AsyncMock(return_value="NO_MEMORY")),
    ):
        response = client.post("/chat", headers=headers, json={"message": prompt})
    assert response.status_code == 200, response.text
    assert search.called
    assert not classify.await_count
    sent_question = answer.await_args.args[0]
    sent_context = answer.await_args.kwargs["context"]
    assert "natural language" in sent_question.lower()
    assert "Do not output JSON" in sent_question
    assert "model announcement" in sent_context
    assert response.json()["research_sources"][0]["url"] == "https://example.com"
