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


class ConversationListResponse(APIModel):
    conversations: list[ConversationRead] = Field(default_factory=list)


class ConversationHistoryMessage(APIModel):
    id: int
    role: ChatRole
    content: str
    created_at: datetime


class ConversationHistoryResponse(APIModel):
    conversation: ConversationRead
    messages: list[ConversationHistoryMessage] = Field(default_factory=list)


SkillTool = Literal["memory", "tavily"]


class SkillCreate(APIModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    instructions: str = Field(min_length=10, max_length=6000)
    enabled_tools: list[SkillTool] = Field(default_factory=lambda: ["memory"], max_length=2)

    @field_validator("name", "instructions")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field must not be blank.")
        return value.strip()

    @field_validator("enabled_tools")
    @classmethod
    def unique_tools(cls, value: list[SkillTool]) -> list[SkillTool]:
        return list(dict.fromkeys(value))


class SkillUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, min_length=10, max_length=6000)
    enabled_tools: list[SkillTool] | None = Field(default=None, max_length=2)

    @field_validator("name", "instructions")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("This field must not be blank.")
        return value.strip() if value is not None else None

    @field_validator("enabled_tools")
    @classmethod
    def unique_optional_tools(cls, value: list[SkillTool] | None) -> list[SkillTool] | None:
        return list(dict.fromkeys(value)) if value is not None else None


class SkillRead(APIModel):
    id: int
    user_id: str
    name: str
    description: str
    instructions: str
    enabled_tools: list[SkillTool] = Field(default_factory=list)
    is_template: bool = False
    created_at: datetime
    updated_at: datetime


class SkillListResponse(APIModel):
    skills: list[SkillRead] = Field(default_factory=list)


class SkillRunRequest(APIModel):
    input: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=128)

    @field_validator("input")
    @classmethod
    def input_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Skill input must not be blank.")
        return value.strip()


class SkillRunResponse(APIModel):
    skill_id: int
    skill_name: str
    conversation_id: str
    answer: str
    model: str
    research_sources: list[ResearchSource] = Field(default_factory=list)
    memories_used: list[str] = Field(default_factory=list)
    tools_used: list[SkillTool] = Field(default_factory=list)
