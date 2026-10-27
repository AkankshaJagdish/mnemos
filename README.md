# Mnemos

**Mnemos is a personal research assistant with persistent memory.** It combines a Streamlit interface, a FastAPI backend, SQLite persistence, NVIDIA Nemotron inference through Nebius Token Factory, and optional live web research through Tavily.

The implementation is an MVP. Model IDs and API access can vary by account; verify the selected models in the Token Factory catalog before relying on them.

## Features

- Account registration and login using email and password.
- Passwords stored as PBKDF2 hashes, not plaintext.
- Signed bearer tokens for protected API endpoints.
- User-scoped memories and conversations: the backend derives the user identity from the token rather than trusting a client-supplied user ID.
- SQLite persistence for user data, memories, conversations, and messages.
- Nebius Token Factory access through the OpenAI-compatible Python SDK.
- Optional Tavily web research with source links.
- Visible memory bank and a control to clear saved memories.
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
    |-- /memories
    |
    |-- agent_service -> memory_service -> SQLite
    |                  research_service -> Tavily (optional)
    |                  model_client -> Nebius Token Factory
    v
SQLite database
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
| `GET` | `/memories` | List the signed-in user's memories | Yes |
| `POST` | `/memories` | Save a memory for the signed-in user | Yes |
| `DELETE` | `/memories` | Clear the signed-in user's saved memories | Yes |
| `GET` | `/health` | Basic service status | No |

The API ignores any user ID submitted by the client for operations that use account identity. It derives the owner from the verified bearer token.

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

## How Mnemos uses Tavily

If `TAVILY_API_KEY` is set, the research service can submit search requests to Tavily and pass the returned evidence and URLs to the agent. If the key is missing, the application skips live research. API errors should be checked in the backend logs. Tavily's Python SDK and API examples are available at <https://github.com/tavily-ai/tavily-python>; this MVP currently uses a direct HTTP request in `research_service.py`.

## Security and MVP limitations

- Configure a unique, high-entropy `MNEMOS_AUTH_SECRET` for every deployed environment. Rotating it invalidates existing bearer tokens.
- Use HTTPS in public deployments. The API itself does not terminate TLS.
- Account identity is derived from signed tokens, and the backend applies user scoping to chat and memory routes.
- This is not a full production identity platform: there is no email verification, password reset, rate limiting, multi-factor authentication, or token revocation.
- The frontend holds the access token in Streamlit session state. Treat the deployment and host as trusted; a production browser application may warrant a different session design.
- SQLite is appropriate for the MVP and modest single-instance use. Use durable storage and evaluate a server database before scaling to multiple replicas.
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
│   │   └── agent_service.py
│   └── routers/
│       ├── auth.py
│       ├── chat.py
│       └── memories.py
├── tests/
│   ├── conftest.py
│   ├── test_chat.py
│   ├── test_memory.py
│   ├── test_research.py
│   └── test_model_client.py
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
