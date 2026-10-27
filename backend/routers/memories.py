"""Database-backed memory endpoints for Mnemos."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from backend.auth import get_current_user
from sqlalchemy.orm import Session
from backend.database import User

from backend.database import get_db
from backend.schemas import (
    ClearMemoriesResponse,
    MemoryCreate,
    MemoryListResponse,
    MemoryRead,
)
from backend.services.memory_service import create_memory, delete_memories, list_memories

router = APIRouter(prefix="/memories", tags=["memory"])


@router.get("", response_model=MemoryListResponse)
def get_memories(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemoryListResponse:
    """List a user's saved memories, newest first."""
    try:
        memories = list_memories(db, user.id, limit=limit)
        return MemoryListResponse(memories=memories)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=MemoryRead, status_code=201)
def add_memory(
    payload: MemoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemoryRead:
    """Explicitly add a memory to the user's memory bank."""
    try:
        return create_memory(db, user.id, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("", response_model=ClearMemoriesResponse)
def clear_memories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClearMemoriesResponse:
    """Delete only this user's saved memories; conversation history remains intact."""
    try:
        deleted_count = delete_memories(db, user.id)
        return ClearMemoriesResponse(status="ok", deleted_count=deleted_count)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
