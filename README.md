# Mnemos

**Your research, with continuity.**

Mnemos is a personal research assistant that carries useful context across conversations. It combines persistent, account-scoped memory, saved research workflows, live web search through Tavily, and NVIDIA Nemotron inference served by Nebius Token Factory.

Instead of treating every chat as a blank slate, Mnemos can retrieve relevant memories and prior work, research current questions, and run repeatable workflows such as Research Brief, Continue My Work, and Decision Memo. Conversation history and skill results remain available when the user returns.

> **Project status:** Hackathon MVP. The hosted application uses a configured PostgreSQL database; local development defaults to SQLite. Provider access, model availability, and live-service performance depend on the deployment's credentials and configuration. See [Limitations and security](#limitations-and-security).

- **Live demo:** https://mnemosakankshajagdish.streamlit.app
- **Source code:** https://github.com/AkankshaJagdish/mnemos
- **Track:** Personal AI
- **License:** MIT

## Why Mnemos

Research work is cumulative. A useful assistant should retain the user's durable preferences and relevant project context, reconnect a new question to earlier work, and retrieve current evidence when the answer depends on changing information.

Mnemos combines three capabilities:

1. **Memory:** save and retrieve user-scoped preferences and useful context across conversations.
2. **Research:** search the web with Tavily and preserve source links alongside generated answers.
3. **Reusable skills:** run saved workflows against the user's input, relevant memory, recent work, and permitted tools.

The user can inspect saved memories, manage workflows, reopen previous conversations, and clear saved memories.

## Features

- Account registration and sign-in.
- Password hashing and signed bearer-token authentication.
- Server-side account identity: protected operations derive the user from the verified token rather than trusting a client-supplied user ID.
- Persistent user-scoped memories, conversations, and messages.
- Relevance-based memory retrieval using lightweight token overlap.
- Memory Bank UI and memory deletion.
- Pattern-based email and phone-number redaction before memory persistence.
- Tavily-powered web search with source URLs and evidence snippets.
- Three editable starter skills:
  - **Research Brief:** gather current evidence and produce a structured, source-linked brief.
  - **Continue My Work:** recover relevant saved context and recent conversation history, identify unresolved questions, and suggest next steps.
  - **Decision Memo:** structure a decision around options, evidence, trade-offs, risks, and a recommendation.
- Custom skills with an allowlist of supported tools (`memory`, `tavily`). Skills are instructions, not arbitrary executable code.
- Skill invocations and outputs are persisted as ordinary messages in the active conversation.
- Streaming chat with a non-streaming fallback path.
- Controlled reasoning-model-to-Nano fallback for eligible failures, with streaming fallback only before any text has been emitted.
- Automated tests for core application behavior and mocked provider integrations.

## Architecture

```text
                         USER
                          |
                          v
               Streamlit frontend
                 frontend/app.py
                          |
                 HTTPS / HTTP API
                 bearer-token auth
                          |
                          v
                    FastAPI API
                  backend/main.py
                          |
        +-----------------+-------------------+
        |                 |                   |
        v                 v                   v
   Auth / users      Chat orchestration    Saved skills
        |                 |                   |
        |                 +---------+---------+
        |                           |
        v                           v
  SQLAlchemy data layer       Agent / model client
        |                           |
        v                +----------+-----------+
  PostgreSQL hosted      |                      |
  SQLite local           v                      v
                    Nebius Token Factory      Tavily Search
                    NVIDIA Nemotron           live web evidence
                    Super + Nano              URLs + snippets
```

### Request lifecycle

1. The user submits a question or runs a saved skill in Streamlit.
2. FastAPI validates the request and authenticates the account.
3. Mnemos retrieves relevant memories and, where appropriate, recent conversation context.
4. The agent determines whether the question needs current web information.
5. When research is enabled and configured, the research service calls Tavily Search and collects result snippets and source URLs.
6. The model client sends the prompt and selected context to the configured NVIDIA Nemotron model through Nebius Token Factory.
7. Eligible transient reasoning-model failures can trigger one Nano fallback attempt. Streaming does not restart after text has been emitted, avoiding duplicated output.
8. Mnemos persists conversation messages and eligible memory candidates in the configured database.
9. The frontend displays the response, research sources, and updated memory or conversation history.

### Main components

| Component | Responsibility |
| --- | --- |
| Streamlit | Sign-in, chat, conversation history, Memory Bank, saved skills |
| FastAPI | API, authentication, validation, orchestration |
| SQLAlchemy | Database models and persistence |
| PostgreSQL / SQLite | Accounts, memories, conversations, messages, skills |
| Model client | Nebius Token Factory chat completions, streaming, model selection and fallback |
| Memory service | Memory extraction support, redaction, relevance retrieval, deletion |
| Research service | Tavily Search requests, evidence snippets and source metadata |
| Skill service | User-owned workflows composed from memory, Tavily and Nemotron |

## How we use NVIDIA Nemotron and Nebius

Mnemos uses NVIDIA Nemotron models served through **Nebius Token Factory**, using its OpenAI-compatible chat-completions API and the OpenAI Python SDK.

### Configured model IDs

The current repository defaults are:

| Role | Model ID | Intended use |
| --- | --- | --- |
| Reasoning model | `nvidia/nemotron-3-super-120b-a12b` | Main responses, research synthesis, and structured workflow output |
| Fast model | `nvidia/Nemotron-3-Nano-30B` | Lightweight classification, memory extraction, and eligible fallback |

The IDs above are the values configured in the repository. Model names and access can vary by account and catalog version. Confirm both exact IDs against the model catalog available to the deployment before relying on them.

### Token Factory endpoints

The current `backend/config.py` default is:

```text
https://api.tokenfactory.nebius.com/v1
```

The base URL is configurable through `NEBIUS_TOKEN_FACTORY_BASE_URL`. Nebius's published quick-start also documents the regional endpoint:

```text
https://api.tokenfactory.us-central1.nebius.com/v1/
```

These are separate hostnames. Mnemos does not silently switch between them; configure the endpoint appropriate to the account and deployment, and verify it with a real request.

The API reference is available at <https://api.tokenfactory.nebius.com/docs>.

### Why two model sizes

The application separates the main reasoning path from lighter supporting tasks. Super is configured for the user-facing reasoning and synthesis path. Nano is configured for small classification and memory-extraction tasks and is also the fallback for eligible reasoning-model failures.

This is an application-level routing design, not a claim that Nano is always faster under every serving condition. Actual latency depends on the model version, endpoint, prompt and output lengths, queueing, region, and traffic. Mnemos does not publish a latency benchmark until a repeatable measurement has been run.

## How we use Tavily

When web research is enabled, Mnemos calls Tavily's Search API at runtime. The research service sends the query, requests a bounded number of results, and passes the returned evidence snippets and URLs to the agent for synthesis. Source links are returned to the interface and retained in saved skill-run messages.

Current integration details:

- Search endpoint: `https://api.tavily.com/search`
- Search depth: `basic` by default (the service also accepts `advanced` internally).
- Maximum results: 5 by default in the agent/skill workflow; the service caps requests at 10.
- Request timeout: 15 seconds by default.
- Raw page content: disabled in the current search request (`include_raw_content: false`).
- If the Tavily key is absent, Mnemos can continue with model-only responses.
- If Tavily fails during a skill run, the workflow can continue without live research.

**Scope clarification:** the current Mnemos research service uses Tavily Search and its returned snippets. It does not currently make a separate Tavily Extract API call. Therefore, this repository demonstrates functional runtime Tavily search, but does not claim a measured benchmark of Tavily's standalone extraction endpoint.

## Setup

### Requirements

- Python 3.11 recommended (the backend Dockerfile uses Python 3.11).
- A Nebius Token Factory API key for model-backed responses.
- A Tavily API key for live web research (optional; search is skipped without it).
- PostgreSQL for a hosted deployment with durable storage, or SQLite for local development.
- Docker is optional for running the backend container.

### 1. Clone and install

```bash
git clone https://github.com/AkankshaJagdish/mnemos.git
cd mnemos

python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in the required values. The application reads environment variables; it does **not** automatically load `.env` files. Export the values in your shell, configure them in your IDE, or use your deployment platform's secret manager.

Minimum configuration for local chat:

- `NEBIUS_TOKEN_FACTORY_KEY`
- `MNEMOS_AUTH_SECRET`

For Tavily research, also set `TAVILY_API_KEY`.

Generate a strong authentication secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

For macOS/Linux, one way to export a local `.env` file is:

```bash
set -a
source .env
set +a
```

Never commit `.env`, API keys, database passwords, or signing secrets.

### 3. Start the backend

From the repository root:

```bash
uvicorn backend.main:app --reload
```

Check:

- Health: <http://127.0.0.1:8000/health>
- Interactive API docs: <http://127.0.0.1:8000/docs>

### 4. Start the frontend

In a second terminal:

```bash
streamlit run frontend/app.py
```

Open the local URL printed by Streamlit, usually <http://localhost:8501>. Register an account and use the chat, memory, conversation-history, and skills controls.

If the backend is hosted elsewhere, set `MNEMOS_API_URL` in the frontend environment to its reachable URL.

## Environment variables

The following names are supported by the current repository configuration. Keep secrets in the deployment environment, not in source control.

| Variable | Required? | Purpose / default |
| --- | --- | --- |
| `NEBIUS_TOKEN_FACTORY_KEY` | Yes for model inference | Token Factory API key. `NEBIUS_API_KEY` is accepted as an alternative. |
| `NEBIUS_API_KEY` | Alternative | Alternative name for the Token Factory API key. |
| `NEBIUS_TOKEN_FACTORY_BASE_URL` | No | Token Factory base URL; defaults to `https://api.tokenfactory.nebius.com/v1`. |
| `NEBIUS_BASE_URL` | No | Legacy alternative base-URL setting if the primary variable is unset. |
| `NEBIUS_REASONING_MODEL` | No | Reasoning model ID; defaults to `nvidia/nemotron-3-super-120b-a12b`. |
| `NEBIUS_FAST_MODEL` | No | Fast model ID; defaults to `nvidia/Nemotron-3-Nano-30B`. |
| `NEBIUS_REQUEST_TIMEOUT` | No | Token Factory request timeout in seconds; defaults to `60`. |
| `TAVILY_API_KEY` | Optional | Enables Tavily live web search. |
| `DATABASE_URL` | No | SQLAlchemy database URL; defaults to `sqlite:///./mnemos.db`. Use PostgreSQL for hosted durable storage. |
| `MNEMOS_AUTH_SECRET` | Yes for secure deployment | Signing secret for authentication tokens. The development fallback must be replaced in any public deployment. |
| `MNEMOS_API_URL` | No | Backend URL used by the Streamlit frontend; defaults to `http://127.0.0.1:8000`. |
| `CORS_ORIGINS` | No | Comma-separated allowed origins; defaults to local Streamlit origins. |
| `APP_NAME` | No | Application name; defaults to `Mnemos`. |
| `APP_VERSION` | No | Application version; defaults to `0.1.0`. |
| `ENVIRONMENT` | No | Environment label; defaults to `development`. |
| `LOG_LEVEL` | No | Logging level; defaults to `INFO`. |
| `MNEMOS_DEMO_MODE` | No | Optional demo-mode flag; defaults to `false`. |
| `MNEMOS_MAX_ANSWER_TOKENS` | No | Application-side completion output cap; defaults to `900`. |
| `MNEMOS_MAX_INPUT_MESSAGES` | No | Maximum messages passed to the model client; defaults to `20`. |
| `MNEMOS_MAX_MESSAGE_CHARS` | No | Character cap per message sent to the model client; defaults to `12000`. |
| `MNEMOS_FRONTEND_TIMEOUT` | No | Frontend HTTP request timeout in seconds; defaults to `90`. |

Application-side token and context bounds help control individual requests. They are not provider-side spending caps or a guarantee of maximum cost.

## API overview

The API is documented interactively at `/docs`. Principal routes include:

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/auth/register` | Register an account |
| `POST` | `/auth/login` | Authenticate and receive a bearer token |
| `GET` | `/auth/me` | Read the authenticated account |
| `POST` | `/chat` | Non-streaming chat |
| `POST` | `/chat/stream` | Streaming chat |
| `GET` | `/conversations` | List the current user's conversations |
| `GET` | `/conversations/{conversation_id}` | Read a conversation owned by the current user |
| `GET` | `/memories` | List the current user's memories |
| `POST` | `/memories` | Add a memory |
| `DELETE` | `/memories` | Delete the current user's saved memories |
| `GET` | `/skills` | List skills and seed starter workflows where needed |
| `POST` | `/skills` | Create a custom skill |
| `PATCH` | `/skills/{skill_id}` | Edit a skill |
| `DELETE` | `/skills/{skill_id}` | Delete a skill |
| `POST` | `/skills/{skill_id}/run` | Run a saved workflow |

## Run tests

```bash
pytest -q
```

The automated suite uses isolated test data and mocks external services where appropriate. Passing offline tests does not prove that a live Token Factory model or Tavily request will succeed. Before a public demonstration, test the configured keys, exact model IDs, endpoint, database persistence, and a full multi-session workflow.

## Deployment notes

The frontend and backend are separate processes/services:

- Deploy the FastAPI backend and configure its provider keys, authentication secret, and durable `DATABASE_URL`.
- Deploy the Streamlit frontend and set `MNEMOS_API_URL` to the backend's public HTTPS URL.
- Configure the backend CORS settings for the actual frontend origin if required by the deployment.
- Use PostgreSQL or another durable database for a hosted instance. Do not rely on an ephemeral container filesystem for SQLite persistence.
- Keep the backend's API keys and database credentials in the host's secret manager.
- Use HTTPS for public traffic.

The public demo currently uses Streamlit for the frontend and FastAPI Cloud for the backend. The hosted database is configured separately from the local SQLite default.

## Limitations and security

Mnemos is a hackathon MVP, not a security-certified or fully production-hardened personal data platform.

- **External processing:** chat content is sent to Nebius Token Factory for inference. When web research is triggered, the query is sent to Tavily. Do not submit credentials, secrets, or information you do not want processed by these providers.
- **Memory redaction:** email addresses and likely phone numbers are pattern-redacted before memory persistence. Pattern matching is imperfect and cannot guarantee detection of every sensitive value.
- **Conversation history:** the memory redaction boundary does not mean all raw conversation messages are redacted. Avoid putting sensitive personal information into chats.
- **Authentication:** password hashing and signed tokens are implemented, and protected operations are account-scoped. The MVP does not include email verification, password reset, MFA, rate limiting, or token revocation.
- **Browser session:** the current frontend's refresh behavior uses a browser-readable cookie. This is not equivalent to an HttpOnly production session.
- **Data ownership:** users can manage their account-scoped records in the application, but hosted data resides in the configured database. “Private” here means application-level account scoping, not local-only storage, end-to-end encryption, or a guarantee that data never leaves the deployment.
- **Model access:** configured model IDs and endpoint permissions must be verified against the Token Factory catalog for the account.
- **Tavily extraction:** the current implementation uses Search API result content, not a separately benchmarked Extract API workflow.
- **NemoClaw/OpenShell:** integration is a future direction, not a currently implemented security boundary.

## Feedback

See [FEEDBACK.md](FEEDBACK.md) for detailed, constructive feedback on Nebius Token Factory, NVIDIA Nemotron, and Tavily. It separates Mnemos implementation facts, public documentation, third-party developer reports, and observations that still require live measurement.

## Project structure

```text
mnemos/
├── frontend/
│   └── app.py
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
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
├── LICENSE
├── README.md
└── FEEDBACK.md
```

## License

MIT. See [LICENSE](LICENSE).
