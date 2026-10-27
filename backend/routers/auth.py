"""Registration and login endpoints for per-user Mnemos data isolation."""
from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import User, get_db
from backend.schemas import AuthLoginRequest, AuthRegisterRequest, AuthResponse
from backend.services.auth_service import create_access_token, hash_password, verify_password

logger = logging.getLogger("mnemos.routers.auth")
router = APIRouter(prefix="/auth", tags=["authentication"])


def _response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        user_id=user.id,
        email=user.email or "",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(
        id=str(uuid4()),
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    return _response(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return _response(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"user_id": user.id, "email": user.email or ""}
