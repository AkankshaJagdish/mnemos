def test_memory_endpoints_require_authentication(client):
    assert client.get("/memories").status_code == 401
    assert client.delete("/memories").status_code == 401

def test_memories_are_isolated_by_account(client, account):
    first, first_headers = account
    second_response = client.post(
        "/auth/register",
        json={"email": "second@example.com", "password": "another-correct-password"},
    )
    assert second_response.status_code == 201
    second = second_response.json()
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}

    created = client.post(
        "/memories",
        headers=first_headers,
        json={"user_id": second["user_id"], "content": "I prefer concise answers."},
    )
    assert created.status_code == 201
    first_list = client.get("/memories", headers=first_headers).json()["memories"]
    second_list = client.get("/memories", headers=second_headers).json()["memories"]
    assert len(first_list) == 1
    assert first_list[0]["content"] == "I prefer concise answers."
    assert second_list == []

    cleared = client.delete("/memories", headers=second_headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted_count"] == 0
    assert len(client.get("/memories", headers=first_headers).json()["memories"]) == 1

def test_manual_memory_redacts_email_and_phone(client, account):
    _, headers = account
    response = client.post(
        "/memories", headers=headers,
        json={"content": "Call me at alex@example.com or +1 (415) 555-0132 about the project."},
    )
    assert response.status_code == 201, response.text
    content = response.json()["content"]
    assert "alex@example.com" not in content
    assert "415" not in content
    assert "[REDACTED_EMAIL]" in content
    assert "[REDACTED_PHONE]" in content


def test_memory_with_only_contact_detail_is_rejected(client, account):
    _, headers = account
    response = client.post("/memories", headers=headers, json={"content": "alex@example.com"})
    assert response.status_code == 422
