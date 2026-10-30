from datetime import datetime, timezone


def test_conversation_history_requires_authentication(client):
    assert client.get("/conversations").status_code == 401
    assert client.get("/conversations/some-thread").status_code == 401


def test_conversation_listing_and_detail_are_user_scoped(client, account):
    from backend.database import Conversation, Message, get_db
    from backend.main import app

    first, headers = account
    # Use the testing database dependency installed by the client fixture.
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    now = datetime.now(timezone.utc)
    try:
        thread = Conversation(id="thread-owned-by-first", user_id=first["user_id"], title="Research notes", created_at=now, updated_at=now)
        db.add(thread)
        db.commit()
        db.add_all([
            Message(conversation_id=thread.id, role="user", content="Question", created_at=now),
            Message(conversation_id=thread.id, role="assistant", content="Answer", created_at=now),
        ])
        db.commit()
    finally:
        db.close()
        generator.close()

    response = client.get("/conversations", headers=headers)
    assert response.status_code == 200, response.text
    assert any(item["id"] == "thread-owned-by-first" for item in response.json()["conversations"])

    detail = client.get("/conversations/thread-owned-by-first", headers=headers)
    assert detail.status_code == 200, detail.text
    assert [item["content"] for item in detail.json()["messages"]] == ["Question", "Answer"]

    second_response = client.post("/auth/register", json={"email": "second@example.com", "password": "another-correct-password"})
    second_headers = {"Authorization": f"Bearer {second_response.json()['access_token']}"}
    assert client.get("/conversations/thread-owned-by-first", headers=second_headers).status_code == 404
