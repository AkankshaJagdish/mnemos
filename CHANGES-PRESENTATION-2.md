# Mnemos presentation and history update

## Scope

- Added authenticated, user-scoped conversation listing and read-only history endpoints.
- Added sidebar controls to open saved conversations and begin a new chat without deleting prior database records.
- Added configurable model output-token caps and input-context bounds.
- Documented a dated public pricing snapshot, example model-completion costs, provider quota checks, and demo usage policy.
- Added a small standalone cost-estimator helper and unit tests; estimates cover one completion only.

## Complete replacement files

- `frontend/app.py` — saved conversation sidebar, new-chat control, compact landing-page spacing.
- `backend/routers/conversations.py` — authenticated list/detail endpoints with user ownership checks.
- `backend/services/agent_service.py` — conversation query helpers.
- `backend/schemas.py` — response models for conversation list/detail.
- `backend/main.py` — registers the conversation router.
- `backend/services/model_client.py` — configurable output cap and bounded model context.
- `tests/test_conversations.py` — list/detail and ownership tests.
- `backend/services/cost_estimator.py`, `tests/test_cost_estimator.py` — transparent illustrative cost calculation.
- `tests/test_model_client.py` — input-context bound test.
- `README.md` — usage limits, current pricing-card workflow, and saved-history API.

## Cost-control caveat

Application token limits reduce answer length and context size. They do not enforce a hard-dollar spending cap because input tokens, auxiliary classification/memory calls, retries, model-specific rates, and Tavily queries also affect cost. Use provider-side usage dashboards and alerts.

## Validation status

`python -m py_compile` passed for the changed Python modules and tests. The offline test suite completed successfully: `31 passed`. Python compilation also passed for the changed modules and tests. These are mocked/offline tests; they do not replace live Nebius, Tavily, Supabase, or hosted UI checks.
