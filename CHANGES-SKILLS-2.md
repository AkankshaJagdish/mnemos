# Mnemos — Skills conversation-history fix (Update 4)

## Problem corrected

Previously, a skill run returned a result to the Streamlit UI but did not persist it as part of a conversation. It could be dismissed or disappear when navigating/reloading, and it was absent from the conversation-history endpoint.

## Changes

- `SkillRunRequest` now accepts an optional `conversation_id`.
- `SkillRunResponse` returns the conversation ID containing the run.
- Skill execution attaches to the currently active conversation when the authenticated user owns it. Otherwise it creates a new conversation owned by that user. A foreign user's conversation ID is never used.
- Skill execution persists a user message identifying the workflow and its input, followed by the assistant result, using the existing `Conversation` and `Message` tables.
- Tavily source links are embedded as Markdown links in the persisted assistant message, so they remain clickable when a saved conversation is reopened.
- Streamlit passes its active conversation ID to the skill endpoint, appends both turns to the visible chat transcript, and renders the output using the same chat history path as ordinary messages.
- Removed the separate transient skill-result panel to avoid duplicate display.
- README documents the persistence behavior and API contract.

## Files rewritten

- `backend/schemas.py`
- `backend/services/skill_service.py`
- `backend/routers/skills.py`
- `frontend/app.py`
- `tests/test_skills.py`
- `README.md`

## Validation

- `PYTHONPATH=. python -m pytest -q`: 38 passed.
- Python compilation for backend and frontend: passed.
- Tests use mocked model and Tavily calls; live provider and deployed-host checks remain intentionally deferred.

## Deployment

Deploy the updated backend and frontend together. No new database table or migration is required for this fix: it reuses the existing `conversations` and `messages` tables. Existing skill records and conversation history remain intact.
