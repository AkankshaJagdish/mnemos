# Mnemos — Skills MVP (Update 3)

## What changed

This package is a complete replacement for the Update 2 package, with a minimal saved-skills feature added without changing the project’s existing Nebius, Tavily, memory, authentication, chat, streaming, conversation-history, or cost-control direction.

- Added the persistent `Skill` SQLAlchemy model and additive `users.skills_initialized` migration. Existing data is preserved.
- Added the authenticated `/skills` API: list, create, edit, delete, and run. Every operation is scoped to the authenticated account; clients cannot supply an owner ID.
- Added three seeded, editable workflows: **Research Brief**, **Continue My Work**, and **Decision Memo**. The templates are created once per account; deleting all skills does not cause them to reappear.
- Added custom user-defined workflows. A skill stores a name, description, workflow instructions, and an allowlist of `memory` and/or `tavily`. No arbitrary Python, shell, or dynamic tool execution is supported.
- Added skill execution using the existing `memory_service`, `research_service`, and `model_client`. Tavily is optional and failures are non-fatal; source links and tool-use metadata are returned when available.
- Added Streamlit sidebar controls to select/run skills, edit saved workflow instructions and tool permissions, and create/delete custom workflows. Results and source links appear in the main view.
- Added API and service tests for starter templates, CRUD, user isolation, tool wiring, and deleting all skills.
- Updated README API docs, architecture, feature description, and online implementation references.

## API

- `GET /skills` — list saved workflows and initialize starter workflows on first access
- `POST /skills` — create a custom workflow
- `PATCH /skills/{skill_id}` — edit a workflow
- `DELETE /skills/{skill_id}` — delete a workflow
- `POST /skills/{skill_id}/run` — execute a workflow with `{"input":"..."}`

## Validation performed

- Python compilation: pass
- Offline automated test suite: see the final test count in the delivery response
- Live Nebius, Tavily, deployed FastAPI Cloud, deployed Streamlit, and hosted database connectivity: **not tested here**; perform the requested live verification after deploying this package.

## Deployment notes

1. Replace the deployed backend files with this package and redeploy FastAPI Cloud. Keep the existing secrets and database URL.
2. `init_db()` creates the new `skills` table and adds `users.skills_initialized` to existing databases. For hosted PostgreSQL, confirm the deployment role has permission to create the table and add a column.
3. Deploy the updated `frontend/app.py` to Streamlit and confirm `MNEMOS_API_URL` points to the updated backend.
4. Sign in, open Saved skills, run Research Brief on a current topic, and verify source links. Test Continue My Work after saving memory and Decision Memo with a concrete decision.

## References used

- FastAPI relational database/session and CRUD pattern: https://fastapi.tiangolo.com/tutorial/sql-databases/
- Tavily use-case workflow principles: https://github.com/tavily-ai/Use-Case-Skills
- Existing project plan, code/source plan, and implementation comparison supplied with the task.
