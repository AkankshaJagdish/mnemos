"""Chat API routes: standard JSON response and optional Server-Sent Events stream."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import get_settings
from backend.database import User, get_db
from backend.schemas import ChatRequest, ChatResponse
from backend.services.agent_service import handle_chat, handle_chat_stream
from backend.services.model_client import ModelClientError, ModelNotConfiguredError

logger = logging.getLogger("mnemos.routers.chat")
router = APIRouter(tags=["chat"])


def _check_provider_configured() -> None:
    if not get_settings().has_nebius_key:
        raise HTTPException(
            status_code=503,
            detail="Nebius Token Factory is not configured. Set NEBIUS_TOKEN_FACTORY_KEY (or NEBIUS_API_KEY) and restart the backend.",
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ChatResponse:
    """Run one ordinary chat turn. Kept for compatibility and non-streaming clients."""
    _check_provider_configured()
    try:
        return await handle_chat(db, payload.model_copy(update={"user_id": user.id}))
    except ModelNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModelClientError as exc:
        logger.warning("Chat request could not be completed: %s", exc)
        raise HTTPException(status_code=502, detail="The model request failed, including any eligible Nano fallback. Check backend logs and provider configuration.") from exc
    except Exception as exc:
        logger.exception("Unexpected chat request failure")
        raise HTTPException(status_code=500, detail="The chat request failed unexpectedly. Check the backend logs.") from exc


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    """Stream chat tokens using SSE; errors are emitted as SSE events after headers start."""
    _check_provider_configured()
    scoped_payload = payload.model_copy(update={"user_id": user.id})

    async def events() -> AsyncIterator[str]:
        try:
            async for event in handle_chat_stream(db, scoped_payload):
                yield "data: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"
        except ModelNotConfiguredError as exc:
            yield "data: " + json.dumps({"type": "error", "detail": str(exc)}) + "\n\n"
        except ModelClientError as exc:
            logger.warning("Streaming chat failed: %s", exc)
            yield "data: " + json.dumps({"type": "error", "detail": "The model stream failed. The ordinary /chat endpoint remains available."}) + "\n\n"
        except Exception:
            logger.exception("Unexpected streaming chat failure")
            yield "data: " + json.dumps({"type": "error", "detail": "Streaming failed unexpectedly. Try the ordinary chat path."}) + "\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
