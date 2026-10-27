"""Pydantic request/response schemas shared by Mnemos API routes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChatRole = Literal["user", "assistant"]


class APIModel(BaseModel):
    """Base schema with ORM serialization support."""
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ChatMessage(APIModel):
    role: ChatRole
    content: str = Field(min_length=1, max_length=20_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class ChatRequest(APIModel):
    message: str = Field(min_length=1, max_length=20_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)
    user_id: str = Field(default="local-user", min_length=1, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    use_web_research: bool | None = None

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_id must not be blank")
        return value.strip()


class ResearchSource(APIModel):
    title: str = Field(default="Source", max_length=500)
    url: str = Field(min_length=1, max_length=2_000)
    snippet: str | None = Field(default=None, max_length=10_000)


class ChatResponse(APIModel):
    answer: str
    model: str
    conversation_id: str | None = None
    research_sources: list[ResearchSource] = Field(default_factory=list)
    memories_used: list[str] = Field(default_factory=list)


class MemoryCreate(APIModel):
    user_id: str = Field(default="local-user", min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value.strip()


class MemoryRead(APIModel):
    id: int
    user_id: str
    content: str
    created_at: datetime
    updated_at: datetime | None = None


class MemoryListResponse(APIModel):
    memories: list[MemoryRead] = Field(default_factory=list)


class ClearMemoriesResponse(APIModel):
    status: Literal["ok"]
    deleted_count: int = Field(ge=0)


class ConversationRead(APIModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ErrorResponse(APIModel):
    detail: str


class AuthRegisterRequest(APIModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return normalized


class AuthLoginRequest(APIModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return normalized


class AuthResponse(APIModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user_id: str
    email: str
