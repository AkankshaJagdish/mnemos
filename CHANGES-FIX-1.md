# Mnemos Fix 1 — Current deployed symptoms

This revision addresses the reported behaviors from the deployed Streamlit/FastAPI/Supabase MVP.

## Findings from the current main branch

1. Streamlit keeps the access token only in `st.session_state`. A browser refresh creates a new Streamlit WebSocket session, so that state is lost even though the account and rows remain in PostgreSQL.
2. The UI had only “Clear conversation,” not a named “New chat” action.
3. Memory extraction was entirely dependent on a secondary model response. A `NO_MEMORY` result skipped storage, and unexpected extraction errors could occur after messages were saved. Explicit stable preferences had no safe non-model fallback.
4. The model client treated any non-empty text as a good answer. It did not reject an internal tool-plan JSON object, so it could display a tool routing object instead of a natural-language synthesis even when Tavily source results had arrived.
5. Old tool-plan JSON already persisted in a conversation could enter future history and further confuse the model.

## Changes in this revision

- `frontend/app.py`: new split landing/login view, new chat button, and best-effort 7-day cookie-based token restore validated through `/auth/me`. The existing API, chat and memory screens remain in place. Research-like prompts use the JSON endpoint (which can reject and retry an invalid tool-plan answer before displaying it); ordinary messages still prefer streaming.
- `backend/services/agent_service.py`: explicit/current-information request detection no longer depends entirely on model classification; clear natural-language research instructions; filters known historical tool-plan strings out of message history; conservative fallback saves explicitly stated durable preferences if the extractor returns `NO_MEMORY` or fails; memory failures do not invalidate a generated answer.
- `backend/services/model_client.py`: rejects recognized visible tool-plan JSON and retries once with Nano; adds a targeted plain-language instruction to the Nano retry; ordinary transient-failure fallback remains.
- `requirements.txt`: adds `streamlit-cookies-controller` for Streamlit browser-cookie support.
- `tests/test_chat.py`: regressions for explicit preference persistence, extractor errors, and a forced research request with source evidence.
- `tests/test_model_client.py`: regression for rejecting tool-plan JSON and retrying with Nano.

## Validation performed

- `python -m py_compile frontend/app.py backend/services/agent_service.py backend/services/model_client.py backend/services/memory_service.py backend/services/research_service.py tests/*.py`
- `python -m pytest -q`: **25 passed**.

These tests mock provider requests. They do not establish that the deployed Nebius models, Tavily key, Streamlit cookie restoration or Supabase network connection works live. Recheck live services after redeployment.

## Deployment notes

1. Apply the complete replacement files in this package to the same paths in GitHub.
2. Let Streamlit Community Cloud install the new `streamlit-cookies-controller` requirement and redeploy.
3. Let FastAPI Cloud redeploy the updated backend code. Database schema changes are not expected for these fixes.
4. Test login, browser refresh, new chat, a stable preference prompt, and current web research.

## Auth cookie caveat

The Streamlit cookie controller cookie is browser-readable by JavaScript; it is not an HttpOnly session cookie. It improves refresh persistence for this MVP but is not an ideal production auth design. It is scoped to the deployed Streamlit site and validated against `/auth/me`. Do not use this application for sensitive accounts or confidential data. A stronger future design would use a backend-controlled HttpOnly cookie or a dedicated auth provider.
