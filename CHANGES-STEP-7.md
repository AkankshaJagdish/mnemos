# Mnemos Step 7 — privacy, fallback, and streaming

This revision preserves the existing FastAPI + Streamlit + SQLite + Nebius Token Factory + Tavily architecture and adds the requested MVP hardening.

## Changes

- `backend/services/memory_service.py`: email and likely-phone redaction is enforced immediately before memory persistence for both manual and automatic memories. Redaction-only memories are rejected; automatic candidates are filtered conservatively.
- `backend/services/model_client.py`: eligible transient reasoning-model failures retry once with Nano. Non-retryable failures do not trigger a retry. The client reports which model actually answered. Streaming can retry with Nano only before the first token; it will not restart after partial output.
- `backend/services/agent_service.py`: regular and streaming paths share context preparation and finalization. Automatic memory extraction sees only sanitized user text and does not use assistant-generated text as memory input.
- `backend/routers/chat.py`: existing JSON `POST /chat` remains available. New authenticated `POST /chat/stream` emits Server-Sent Events with token events and final response metadata.
- `frontend/app.py`: prefers the streaming endpoint and falls back to JSON chat if streaming is unavailable before output begins. It does not silently restart after partial output. The UI explains that inference/search providers receive the relevant data.
- `README.md`: documents privacy behavior, fallback behavior, streaming endpoint, and limitations.
- Tests cover PII redaction, automatic memory extraction inputs, retry eligibility, successful Nano fallback, failure of both models, streaming fallback, partial-stream behavior, and the SSE route.

## Local test result

`PYTHONPATH=. python -m pytest -q` — 21 passed.

`PYTHONPATH=. python -m compileall -q backend frontend tests` — passed.

These are offline tests with mocked model calls. Per the project plan, live Nebius/Tavily connectivity checks and end-to-end deployment validation have not been run in this step.

## Privacy limitation

PII detection is pattern-based and cannot guarantee detection of every email/phone representation. This change redacts memory content; it does not remove PII from raw persisted chat history. Chat content is sent to Nebius for inference, and queries may be sent to Tavily when research is used.
