def test_skill_routes_require_authentication(client):
    assert client.get("/skills").status_code == 401
    assert client.post("/skills", json={"name": "A workflow", "instructions": "Do useful work."}).status_code == 401


def test_starter_skills_are_created_and_user_scoped(client, account):
    _, headers = account
    response = client.get("/skills", headers=headers)
    assert response.status_code == 200, response.text
    skills = response.json()["skills"]
    assert [item["name"] for item in skills] == ["Research Brief", "Continue My Work", "Decision Memo"]
    assert skills[0]["enabled_tools"] == ["memory", "tavily"]
    assert skills[1]["enabled_tools"] == ["memory"]
    assert client.get("/skills", headers=headers).json()["skills"] == skills


def test_create_update_delete_skill_and_prevent_cross_user_access(client, account):
    _, headers = account
    created = client.post("/skills", headers=headers, json={
        "name": "Weekly Review", "description": "Review progress", 
        "instructions": "Summarize progress, risks, and next actions.",
        "enabled_tools": ["memory"],
    })
    assert created.status_code == 201, created.text
    skill = created.json()
    assert skill["is_template"] is False

    second = client.post("/auth/register", json={"email": "second@example.com", "password": "another-correct-password"})
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
    assert client.patch(f"/skills/{skill['id']}", headers=second_headers, json={"name": "Hijack"}).status_code == 404
    assert client.delete(f"/skills/{skill['id']}", headers=second_headers).status_code == 404

    updated = client.patch(f"/skills/{skill['id']}", headers=headers, json={"name": "Project Weekly Review", "enabled_tools": ["memory", "tavily"]})
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Project Weekly Review"
    assert updated.json()["enabled_tools"] == ["memory", "tavily"]
    deleted = client.delete(f"/skills/{skill['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "ok"


def test_run_skill_uses_allowlisted_memory_and_tavily_services(client, account, monkeypatch):
    _, headers = account
    skill_response = client.get("/skills", headers=headers)
    research_skill = next(item for item in skill_response.json()["skills"] if item["name"] == "Research Brief")

    import backend.routers.skills as skill_router
    import backend.services.skill_service as skill_service
    from backend.schemas import ResearchSource

    class FakeSettings:
        has_nebius_key = True

    async def fake_answer(prompt, *, history=(), context=None, max_tokens=1200):
        assert "Research Brief" in prompt
        assert context and "Tavily search evidence" in context
        return "Evidence-led brief", "test-model"

    monkeypatch.setattr(skill_router, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(skill_service.model_client, "answer_with_model", fake_answer)
    monkeypatch.setattr(skill_service, "tavily_configured", lambda: True)
    monkeypatch.setattr(skill_service, "search_web", lambda *args, **kwargs: (
        "Title: Official source\nURL: https://example.com\nEvidence: supported claim",
        [ResearchSource(title="Official source", url="https://example.com", snippet="supported claim")],
    ))

    response = client.post(f"/skills/{research_skill['id']}/run", headers=headers, json={"input": "Research the latest topic"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["answer"] == "Evidence-led brief"
    assert result["model"] == "test-model"
    assert result["tools_used"] == ["memory", "tavily"]
    assert result["research_sources"][0]["url"] == "https://example.com"
    assert result["conversation_id"]
    history = client.get(f"/conversations/{result['conversation_id']}", headers=headers)
    assert history.status_code == 200, history.text
    saved_messages = history.json()["messages"]
    assert len(saved_messages) == 2
    assert saved_messages[0]["role"] == "user"
    assert "Research Brief" in saved_messages[0]["content"]
    assert saved_messages[1]["role"] == "assistant"
    assert "Evidence-led brief" in saved_messages[1]["content"]
    assert "https://example.com" in saved_messages[1]["content"]


def test_skill_run_rejects_other_users_skill(client, account):
    _, headers = account
    skill = client.get("/skills", headers=headers).json()["skills"][0]
    second = client.post("/auth/register", json={"email": "other@example.com", "password": "another-correct-password"})
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
    response = client.post(f"/skills/{skill['id']}/run", headers=second_headers, json={"input": "Do this"})
    assert response.status_code == 404


def test_deleting_all_skills_does_not_recreate_templates(client, account):
    _, headers = account
    skills = client.get("/skills", headers=headers).json()["skills"]
    for skill in skills:
        response = client.delete(f"/skills/{skill['id']}", headers=headers)
        assert response.status_code == 200
    assert client.get("/skills", headers=headers).json()["skills"] == []


def test_skill_run_appends_to_active_conversation(client, account, monkeypatch):
    _, headers = account
    skill = client.get("/skills", headers=headers).json()["skills"][1]
    import backend.routers.chat as chat_router
    import backend.services.agent_service as agent_service
    import backend.routers.skills as skill_router
    import backend.services.skill_service as skill_service

    class FakeSettings:
        has_nebius_key = True

    async def fake_answer(prompt, *, history=(), context=None, max_tokens=1200):
        return "Next steps from the skill", "test-model"

    async def fake_chat_answer(prompt, *, history=(), context=None, max_tokens=1600):
        return "Initial project response", "test-model"

    async def no_research(_message):
        return False

    async def no_memory(_message):
        return "NO_MEMORY"

    monkeypatch.setattr(chat_router, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(agent_service.model_client, "answer_with_model", fake_chat_answer)
    monkeypatch.setattr(agent_service.model_client, "classify_research_need", no_research)
    monkeypatch.setattr(agent_service.model_client, "summarize_memory", no_memory)
    chat = client.post("/chat", headers=headers, json={"message": "Initial project context"})
    assert chat.status_code == 200, chat.text
    conversation_id = chat.json()["conversation_id"]

    monkeypatch.setattr(skill_router, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(skill_service.model_client, "answer_with_model", fake_answer)
    result = client.post(f"/skills/{skill['id']}/run", headers=headers, json={
        "input": "Continue the project", "conversation_id": conversation_id,
    })
    assert result.status_code == 200, result.text
    assert result.json()["conversation_id"] == conversation_id
    history = client.get(f"/conversations/{conversation_id}", headers=headers)
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert len(messages) == 4
    assert messages[-2]["role"] == "user"
    assert "Continue My Work" in messages[-2]["content"]
    assert messages[-1]["role"] == "assistant"
    assert "Next steps from the skill" in messages[-1]["content"]
