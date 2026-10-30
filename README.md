# Mnemos

**Mnemos is a personal research assistant with persistent memory.** It combines a Streamlit interface, a FastAPI backend, SQLAlchemy-backed persistence (SQLite locally; PostgreSQL recommended for hosted persistent storage), NVIDIA Nemotron inference through Nebius Token Factory, and optional live web research through Tavily.

The implementation is an MVP. Model IDs and API access can vary by account; verify the selected models in the Token Factory catalog before relying on them.

## Features

- Account registration and login using email and password.
- Passwords stored as PBKDF2 hashes, not plaintext.
- Signed bearer tokens for protected API endpoints.
- User-scoped memories and conversations: the backend derives the user identity from the token rather than trusting a client-supplied user ID.
- SQLAlchemy-backed persistence (SQLite locally; PostgreSQL recommended for hosted persistent storage) for user data, memories, conversations, and messages.
- Nebius Token Factory access through the OpenAI-compatible Python SDK.
- Optional Tavily web research with source links.
- Visible memory bank and a control to clear saved memories.
- User-owned saved skills: editable Research Brief, Continue My Work, and Decision Memo workflows, plus custom workflows.
- Skills can call the existing memory retrieval service and optional Tavily search through a fixed allowlist; saved skills are instructions, not executable code.
- Automated tests for chat authorization, memory isolation, PII redaction, model fallback, streaming fallback, research behavior, and model-client configuration.

## Architecture

```text
Streamlit frontend (frontend/app.py)
    |
    | HTTP + bearer token
    v
FastAPI backend (backend/main.py)
    |-- /auth/register, /auth/login, /auth/me
    |-- /chat
    |-- /conversations (list/read saved threads)
    |-- /memories
    |-- /skills (CRUD + workflow execution)
    |
    |-- agent_service -> memory_service -> configured SQL database
    |                  research_service -> Tavily (optional)
    |                  model_client -> Nebius Token Factory
    v
SQLite locally; Supabase PostgreSQL on the deployed app
```

`backend/routers/` owns HTTP routes; `backend/services/` owns the model, memory, research, and orchestration logic. The frontend does not connect to SQLite directly.

## Requirements

- Python 3.11 (the Dockerfile uses Python 3.11).
- A Nebius Token Factory API key for model-backed chat.
- A Tavily API key for live web research (optional).
- Docker, if running the backend in a container.

## Local setup

Run commands from the repository root (`mnemos/`).

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows PowerShell
   # .venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set the secrets. The application reads environment variables; `.env` is a template for your local configuration. Export the values in your shell or use your preferred environment loader. Do not commit `.env`.

   Minimum for chat:
   - `NEBIUS_TOKEN_FACTORY_KEY`
   - `MNEMOS_AUTH_SECRET` (use a long random value)

   Optional:
   - `TAVILY_API_KEY` enables live research.
   - `NEBIUS_REASONING_MODEL` and `NEBIUS_FAST_MODEL` override the default model IDs.
   - `DATABASE_URL` changes the database location.
   - `CORS_ORIGINS` sets the allowed browser origins if you later add a browser-based frontend.

   Generate a signing secret with:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   The Python application does not automatically load `.env` files. Export variables before starting the processes, or configure them through your IDE or deployment platform. For example, on macOS/Linux:

   ```bash
   set -a
   source .env
   set +a
   ```

4. Start the API in terminal one:

   ```bash
   uvicorn backend.main:app --reload
   ```

   Check `http://127.0.0.1:8000/health` and open `http://127.0.0.1:8000/docs` for the API documentation. The database tables are initialized at API startup.

5. Start Streamlit in terminal two:

   ```bash
   streamlit run frontend/app.py
   ```

   Open the local URL Streamlit prints (usually `http://localhost:8501`). Register an account, then use the chat and memory bank.

If the backend runs on another host or port, set `MNEMOS_API_URL` for the frontend to the backend's reachable URL. In a containerized deployment, `127.0.0.1` from the frontend container refers to that frontend container, not the API container.

## API overview

| Method | Endpoint | Purpose | Authentication |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | Create an account | No |
| `POST` | `/auth/login` | Sign in and receive a bearer token | No |
| `GET` | `/auth/me` | Return the current account | Yes |
| `POST` | `/chat` | Run a chat turn and receive a complete JSON response | Yes |
| `POST` | `/chat/stream` | Stream tokens and final metadata using Server-Sent Events (SSE) | Yes |
| `GET` | `/conversations` | List the current user's saved conversations | Yes |
| `GET` | `/conversations/{conversation_id}` | Read a saved conversation the user owns | Yes |
| `GET` | `/memories` | List the signed-in user's memories | Yes |
| `POST` | `/memories` | Save a memory for the signed-in user | Yes |
| `DELETE` | `/memories` | Clear the signed-in user's saved memories | Yes |
| `GET` | `/skills` | List saved skills; creates the three starter workflows for a new skill collection | Yes |
| `POST` | `/skills` | Save a custom workflow | Yes |
| `PATCH` | `/skills/{skill_id}` | Edit a saved workflow and its allowed tools | Yes |
| `DELETE` | `/skills/{skill_id}` | Delete a saved workflow | Yes |
| `POST` | `/skills/{skill_id}/run` | Run a workflow using allowed memory/Tavily services and Nebius inference | Yes |
| `GET` | `/health` | Basic service status | No |

The API ignores any user ID submitted by the client for operations that use account identity. It derives the owner from the verified bearer token.

## Saved skills (MVP)

On first opening the Skills section, Mnemos seeds three editable starter workflows for that account:

- **Research Brief** — retrieves relevant saved memories, searches Tavily when configured, and asks Nemotron for a concise brief with evidence, source links, and uncertainties.
- **Continue My Work** — uses relevant memories and recent conversation history to recap context, unresolved decisions, and next actions.
- **Decision Memo** — combines relevant memories and optional Tavily research into options, trade-offs, risks, and a recommendation.

The sidebar can run a skill, edit its instructions and tool permissions, and create custom skills. Skill runs are saved as ordinary user/assistant messages in the active conversation; if there is no active conversation, Mnemos creates one. They therefore appear in the chat transcript immediately and remain available through the existing conversation-history list after reopening the app. Research source links are included in the persisted assistant message. The run request accepts an optional `conversation_id` to continue the active thread. The tool allowlist is deliberately small (`memory`, `tavily`); users cannot save or execute Python, shell commands, or arbitrary tools. Tavily failures are non-fatal: the workflow can continue without live research. Skills and their conversation messages are stored in the same configured SQL database and scoped to the authenticated account.

Implementation references: the database model/session/CRUD structure follows the straightforward relational patterns documented by [FastAPI](https://fastapi.tiangolo.com/tutorial/sql-databases/). Research workflows use the same evidence-first principles highlighted in [Tavily Use-Case Skills](https://github.com/tavily-ai/Use-Case-Skills): focused search, source verification, citation hygiene, and explicit coverage gaps. This service performs Tavily Search followed by bounded Tavily Extract on selected URLs.

## Run tests

```bash
pytest -q
```

Tests use an isolated in-memory SQLite database and mock external API calls where appropriate. They do not require live Nebius or Tavily credentials.

## Docker: backend API

The Dockerfile packages the FastAPI backend. Run Streamlit separately as a frontend service or process.

```bash
docker build -t mnemos-api .
docker run --rm -p 8000:8000 \
  -e NEBIUS_TOKEN_FACTORY_KEY="$NEBIUS_TOKEN_FACTORY_KEY" \
  -e TAVILY_API_KEY="$TAVILY_API_KEY" \
  -e MNEMOS_AUTH_SECRET="$MNEMOS_AUTH_SECRET" \
  -v mnemos-data:/data \
  mnemos-api
```

The named Docker volume persists the SQLite database at `/data/mnemos.db`. Use a strong `MNEMOS_AUTH_SECRET` and keep API keys in your deployment's secret manager. Do not expose a public instance with the default development secret.

## How Mnemos uses NVIDIA Nemotron and Nebius

Mnemos uses the OpenAI-compatible chat completions interface exposed by Nebius Token Factory. The backend's `model_client.py` uses the `openai` Python SDK with the configured Token Factory base URL and API key. The configured reasoning and fast model IDs default to:

- `nvidia/nemotron-3-super-120b-a12b`
- `nvidia/Nemotron-3-Nano-30B`

These defaults reflect the project plan, not a guarantee that both identifiers are enabled for every account. Confirm the currently available model IDs and access in the Token Factory catalog and adjust the environment variables if needed. API reference: <https://api.tokenfactory.nebius.com/docs>.

## How Mnemos uses Tavily Search and Extract

If `TAVILY_API_KEY` is set, the research service performs a two-step retrieval flow using direct HTTP requests in `backend/services/research_service.py`:

1. **Search** calls `POST https://api.tavily.com/search` to discover up to five candidate pages.
2. **Extract** selects up to the top three valid result URLs and calls `POST https://api.tavily.com/extract` with `extract_depth="basic"`, Markdown output, and images disabled.
3. Successfully extracted `raw_content` is provided to the model as evidence and is reflected in each source snippet. If extraction fails, Mnemos falls back to the original search snippets instead of failing the whole research request.

This is an intentional search-then-extract design: it limits extraction to pages surfaced by the query rather than spending requests extracting unfiltered content. Tavily documents this two-step approach as providing more control over source selection; its Extract API accepts one or multiple URLs (up to 20) and returns successful and failed extractions. See [Tavily Extract API](https://help.tavily.com/articles/8721959612-what-is-the-tavily-extract-api) and [Tavily's search-then-extract guidance](https://help.tavily.com/articles/3363168593-extracting-web-content-using-tavily).

When `TAVILY_API_KEY` is absent, live research is skipped. Search failures are reported through the research service error path; extraction failures are logged and use search snippets as fallback. The offline tests mock both API calls; they do not prove live account availability or measure online extraction quality.


## Security and MVP limitations

- Configure a unique, high-entropy `MNEMOS_AUTH_SECRET` for every deployed environment. Rotating it invalidates existing bearer tokens.
- Use HTTPS in public deployments. The API itself does not terminate TLS.
- Account identity is derived from signed tokens, and the backend applies user scoping to chat and memory routes.
- This is not a full production identity platform: there is no email verification, password reset, rate limiting, multi-factor authentication, or token revocation.
- The frontend restores sign-in from a browser-readable cookie for MVP convenience. It is not an HttpOnly production session design; treat the deployment and host as trusted.
- Local development and tests use SQLite. The hosted demo uses the configured Supabase PostgreSQL database for durable accounts, memories, conversations, and messages.
- Do not put passwords, API keys, or other secrets into saved memories or prompts.
- The configured model IDs and API permissions must be verified with the actual account. Live API integration is not covered by the offline test suite.

## Privacy and failure handling

- Email addresses and likely phone numbers are redacted before any memory is persisted, including manually added memories. Detection is pattern-based and cannot guarantee that every sensitive detail is detected.
- Automatic memory extraction considers only the sanitized user message, not the assistant response. The extractor is instructed to avoid sensitive data, and the persistence layer applies redaction again as a final boundary.
- The reasoning model is retried once with the configured Nano model when a reasoning completion fails. If both attempts fail, the request returns an error. Streaming may fall back to Nano only before it emits any text; it does not restart after partial output to avoid duplicated answers.
- The UI prefers streaming but retains `/chat` as a non-streaming fallback when streaming is unavailable before output begins.
- Chat content is sent to Nebius for inference. When research is triggered, the search query is sent to Tavily. Do not use Mnemos for secrets or information you do not want to send to these providers.

## Project structure

```text
mnemos/
├── frontend/app.py
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── schemas.py
│   ├── auth.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── model_client.py
│   │   ├── memory_service.py
│   │   ├── research_service.py
│   │   ├── agent_service.py
│   │   └── skill_service.py
│   └── routers/
│       ├── auth.py
│       ├── chat.py
│       ├── conversations.py
│       ├── memories.py
│       └── skills.py
├── tests/
│   ├── conftest.py
│   ├── test_chat.py
│   ├── test_memory.py
│   ├── test_skills.py
│   ├── test_research.py
│   ├── test_model_client.py
│   ├── test_conversations.py
│   └── test_cost_estimator.py
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
├── LICENSE
├── README.md
└── FEEDBACK.md
```

## License

Mnemos is licensed under the MIT License. See [LICENSE](LICENSE).


## Fix 1 deployment notes (2026-10-29)

The current MVP revision includes a new-chat control, saved conversation history, best-effort browser refresh login restoration, explicit preference memory fallback, filtering of previously persisted tool-plan JSON from future history, and a Nano retry when the reasoning model returns a recognized internal tool-plan object instead of user-facing prose. See `CHANGES-FIX-1.md` and `CHANGES-PRESENTATION-2.md`.

For hosted durable storage, configure the existing `DATABASE_URL` with your Supabase PostgreSQL connection and install the PostgreSQL driver already declared in `requirements.txt`. Do not use a local SQLite file for a hosted instance whose filesystem may be ephemeral.

The cookie-based refresh behavior is an MVP convenience only: the cookie is readable by client-side JavaScript and is not a substitute for an HttpOnly production session.


## Usage limits and cost controls

Mnemos is a hackathon MVP. The owner of the deployed instance pays for provider usage. Free hosting does not make model inference or web research free.

### Application-side bounds

- `MNEMOS_MAX_ANSWER_TOKENS` caps output tokens per completion (default `900`). Set this to `600` or `700` for the judge demo.
- `MNEMOS_MAX_INPUT_MESSAGES` bounds message count passed to the model (default `20`).
- `MNEMOS_MAX_MESSAGE_CHARS` bounds each message's character length (default `12000`). These limits bound output and context size but are **not** a hard dollar budget.
- Each ordinary chat can make more than one model call (for research classification and memory extraction). A failed Super call or recognized internal tool-plan response may trigger one Nano fallback.
- Tavily search defaults to five results and a 15-second timeout. Avoid repetitive exploratory requests during the public demo.

### Recommended settings for a judge demo

Set in FastAPI Cloud environment variables, then redeploy:

```text
MNEMOS_MAX_ANSWER_TOKENS=700
MNEMOS_MAX_INPUT_MESSAGES=16
MNEMOS_MAX_MESSAGE_CHARS=8000
NEBIUS_REQUEST_TIMEOUT=60
```

These are app-level guardrails, not provider-imposed quotas or a guarantee of maximum spend. Do not alter the required NVIDIA Nemotron model IDs simply to control costs; use the configured Super/Nano design and check account usage.

### Pricing and quotas (public rate-card snapshot: 29 October 2026)

The public Nebius Nemotron pricing page currently lists these rates for Token Factory. Rates, model IDs, regions, caching treatment, and account-specific access can change, so verify the model row in your account's [Token Factory catalog](https://tokenfactory.nebius.com/) before the event. Source: [official Nebius Nemotron pricing](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference), checked 29 October 2026.

| Configured model | Input, per 1 million tokens | Output, per 1 million tokens |
|---|---:|---:|
| `nvidia/nemotron-3-super-120b-a12b` | $0.30 | $0.90 |
| `nvidia/Nemotron-3-Nano-30B` (catalog naming may use `Nemotron-3-Nano-30B-A3B`) | $0.06 | $0.24 |

**Token cost example:** an answer request using 4,000 input tokens and 700 output tokens would cost about **$0.00183 on Super** or **$0.000408 on Nano**, before any other model calls. These are illustrative estimates, not the total cost of one chat turn. Classification, automatic memory extraction, fallback retries, and longer accumulated history can add input/output usage.

Tavily's public pricing page currently lists a free Researcher plan with **1,000 API credits per month**, no credit card required, and pay-as-you-go at **$0.008 per credit**. Some request types use more credits than others. Check your [Tavily dashboard](https://app.tavily.com/) and the [official pricing page](https://www.tavily.com/pricing) for the plan actually applied to your API key. Source checked 29 October 2026.

Owner policy:

1. Check Nebius usage and Tavily quota before and after judging; enable any available account-level spending alerts.
2. Use prepared demo prompts, not load testing.
3. Never publish API keys, database URLs, passwords, or auth secrets.
4. If credits or quota approach their limit, pause the public demo or turn off web research rather than permit unbounded use.
5. App token caps are not a global spend ceiling; provider-side usage monitoring remains necessary.

## Saved conversation history

The authenticated API exposes `GET /conversations` to list conversations owned by the signed-in user and `GET /conversations/{conversation_id}` to read a selected thread. Reading history does not rerun the prompt. The Streamlit sidebar lists saved conversations. Selecting a saved thread loads its prior messages and restores that conversation ID, so a follow-up continues that thread. Select **New chat** to begin a separate thread; this does not delete the saved conversation.
