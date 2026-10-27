"""Streamlit frontend for Mnemos with account sign-in and isolated user data."""
import json
import os
from typing import Any

import requests
import streamlit as st

DEFAULT_API_URL = os.getenv("MNEMOS_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("MNEMOS_FRONTEND_TIMEOUT", "90"))

st.set_page_config(
    page_title="Mnemos — Personal Research Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _api_url() -> str:
    try:
        configured = st.secrets.get("MNEMOS_API_URL", DEFAULT_API_URL)
    except Exception:
        configured = DEFAULT_API_URL
    return str(configured).rstrip("/")


def _request_json(method: str, path: str, *, authenticated: bool = True, **kwargs: Any) -> dict[str, Any]:
    headers = dict(kwargs.pop("headers", {}) or {})
    token = st.session_state.get("access_token")
    if authenticated and token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.request(
        method,
        f"{_api_url()}{path}",
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers=headers,
        **kwargs,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("The backend returned an unexpected response format.")
    return data



def _stream_chat(payload: dict[str, Any]) -> tuple[str, dict[str, Any] | None, bool, str | None]:
    """Consume SSE and preserve partial-output state if the connection drops."""
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    response = requests.post(
        f"{_api_url()}/chat/stream", json=payload, headers=headers,
        timeout=(10, REQUEST_TIMEOUT_SECONDS), stream=True,
    )
    try:
        response.raise_for_status()
    except Exception:
        response.close()
        raise

    response.encoding = "utf-8"
    answer = ""
    metadata: dict[str, Any] | None = None
    emitted = False
    error: str | None = None
    placeholder = st.empty()
    try:
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data: "):
                continue
            event = json.loads(raw_line[6:])
            if event.get("type") == "token":
                token = str(event.get("token", ""))
                if token:
                    emitted = True
                    answer += token
                    placeholder.markdown(answer)
            elif event.get("type") == "done":
                metadata = event.get("response") or {}
            elif event.get("type") == "error":
                error = str(event.get("detail", "The stream failed."))
                break
    except (requests.RequestException, ValueError, TypeError) as exc:
        error = f"The stream ended unexpectedly: {exc}"
    finally:
        response.close()
    if not emitted and metadata is None and error is None:
        error = "The stream ended before a response was received."
    return answer, metadata, emitted, error


def _show_backend_status() -> None:
    try:
        status = _request_json("GET", "/health", authenticated=False)
        if status.get("status") == "ok":
            st.caption("Backend connected")
            if not status.get("nebius_configured"):
                st.warning("The backend is running, but its Nebius API key is not configured.")
            if not status.get("tavily_configured"):
                st.caption("Tavily is not configured; current web research is disabled.")
    except requests.RequestException:
        st.caption("Backend not connected — start the FastAPI server to chat.")


for key, default in {
    "access_token": None,
    "account_email": None,
    "user_id": None,
    "messages": [],
    "conversation_id": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def _accept_auth(result: dict[str, Any]) -> None:
    st.session_state.access_token = result["access_token"]
    st.session_state.user_id = result["user_id"]
    st.session_state.account_email = result["email"]
    st.session_state.messages = []
    st.session_state.conversation_id = None


if not st.session_state.access_token:
    st.title("Mnemos")
    st.write("Sign in or create an account. Your memories and conversations are scoped to your account.")
    _show_backend_status()
    tab_login, tab_register = st.tabs(["Sign in", "Create account"])

    with tab_login:
        with st.form("login_form"):
            login_email = st.text_input("Email address", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            login_submit = st.form_submit_button("Sign in", use_container_width=True)
        if login_submit:
            try:
                _accept_auth(_request_json(
                    "POST", "/auth/login", authenticated=False,
                    json={"email": login_email, "password": login_password},
                ))
                st.rerun()
            except requests.HTTPError as exc:
                try:
                    detail = exc.response.json().get("detail", "Sign-in failed.")
                except Exception:
                    detail = "Sign-in failed."
                st.error(str(detail))
            except requests.RequestException:
                st.error("Could not connect to the Mnemos backend.")

    with tab_register:
        with st.form("register_form"):
            register_email = st.text_input("Email address", key="register_email")
            register_password = st.text_input("Password (at least 8 characters)", type="password", key="register_password")
            register_confirm = st.text_input("Confirm password", type="password", key="register_confirm")
            register_submit = st.form_submit_button("Create account", use_container_width=True)
        if register_submit:
            if register_password != register_confirm:
                st.error("The passwords do not match.")
            else:
                try:
                    _accept_auth(_request_json(
                        "POST", "/auth/register", authenticated=False,
                        json={"email": register_email, "password": register_password},
                    ))
                    st.rerun()
                except requests.HTTPError as exc:
                    try:
                        detail = exc.response.json().get("detail", "Account creation failed.")
                    except Exception:
                        detail = "Account creation failed."
                    st.error(str(detail))
                except requests.RequestException:
                    st.error("Could not connect to the Mnemos backend.")
    st.stop()


with st.sidebar:
    st.title("Mnemos")
    st.caption(f"Signed in as {st.session_state.account_email}")
    _show_backend_status()
    if st.button("Sign out", use_container_width=True):
        for key in ("access_token", "account_email", "user_id", "conversation_id"):
            st.session_state[key] = None
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.subheader("Memory Bank")
    try:
        memory_data = _request_json("GET", "/memories")
        memories = memory_data.get("memories", [])
        if memories:
            for memory in memories:
                if isinstance(memory, dict):
                    st.markdown(f"- {memory.get('content', str(memory))}")
        else:
            st.caption("No saved memories yet.")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            st.warning("Your session expired. Sign in again.")
        else:
            st.caption("Memory service is not available.")
    except requests.RequestException:
        st.caption("Memory service is not available.")

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()

    if st.button("Clear saved memories", use_container_width=True, type="secondary"):
        try:
            result = _request_json("DELETE", "/memories")
            st.success(f"Deleted {result.get('deleted_count', 0)} saved memories.")
            st.rerun()
        except requests.RequestException:
            st.error("Could not reach the backend to clear memories.")

st.title("Your research, with continuity")
st.write(
    "Ask a question or continue a line of thought. Mnemos can use your saved memories, "
    "persist conversation history, and run Tavily web research when configured."
)
st.caption("Privacy: Mnemos redacts detected email addresses and phone numbers from saved memories. Chat content may be sent to Nebius for model inference and search queries may be sent to Tavily when web research is used.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Research sources"):
                for source in message["sources"]:
                    title = source.get("title") or source.get("url") or "Source"
                    url = source.get("url")
                    st.markdown(f"- [{title}]({url})" if url else f"- {title}")

prompt = st.chat_input("What would you like to research or think through?")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    history = [
        {"role": item["role"], "content": item["content"]}
        for item in st.session_state.messages[:-1]
        if item.get("role") in {"user", "assistant"}
    ]
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                request_payload = {"message": prompt, "history": history}
                if st.session_state.conversation_id:
                    request_payload["conversation_id"] = st.session_state.conversation_id
                # Prefer streaming for responsiveness. If the stream fails before any
                # text is emitted (for example, an older deployment lacks this route),
                # transparently use the stable JSON endpoint. Never restart after partial output.
                answer, stream_metadata, emitted, stream_error = "", None, False, None
                try:
                    answer, stream_metadata, emitted, stream_error = _stream_chat(request_payload)
                except (requests.RequestException, ValueError, TypeError):
                    stream_error = "Streaming endpoint unavailable before output."
                if stream_metadata is not None:
                    result = stream_metadata
                    answer = str(result.get("answer", answer))
                elif not emitted:
                    result = _request_json("POST", "/chat", json=request_payload)
                    answer = str(result.get("answer", "The backend returned no answer."))
                    st.markdown(answer)
                else:
                    st.warning(stream_error or "The stream ended before completion. This partial answer was not saved; retry your question.")
                    st.stop()
                st.session_state.conversation_id = result.get("conversation_id", st.session_state.conversation_id)
                sources = result.get("research_sources") or []
                if sources:
                    with st.expander("Research sources"):
                        for source in sources:
                            if isinstance(source, dict):
                                title = source.get("title") or source.get("url") or "Source"
                                url = source.get("url")
                                st.markdown(f"- [{title}]({url})" if url else f"- {title}")
                st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
            except requests.HTTPError as exc:
                detail = "The backend rejected the request."
                try:
                    detail = str(exc.response.json().get("detail", detail))
                except Exception:
                    pass
                st.error(detail)
            except requests.RequestException:
                st.error("Could not reach the Mnemos backend. Check MNEMOS_API_URL and confirm the backend is running.")
            except (ValueError, TypeError):
                st.error("The backend returned an invalid response.")
