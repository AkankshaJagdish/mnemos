"""Read-only endpoints for a user's saved conversation history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import User, get_db
from backend.schemas import (
    ConversationHistoryMessage, ConversationHistoryResponse, ConversationListResponse,
)
from backend.services.agent_service import get_conversation_messages, list_user_conversations

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
def get_conversations(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationListResponse:
    """List recent conversation threads belonging to the current account."""
    return ConversationListResponse(conversations=list_user_conversations(db, user.id, limit=limit))


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationHistoryResponse:
    """Read a saved thread only when it belongs to the authenticated account."""
    result = get_conversation_messages(db, user.id, conversation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    conversation, messages = result
    return ConversationHistoryResponse(
        conversation=conversation,
        messages=[ConversationHistoryMessage.model_validate(message) for message in messages],
    )
