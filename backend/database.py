"""SQLite/SQLAlchemy persistence for Mnemos.

Run from the repository root. The database URL is configured in backend.config.
This module provides the database foundation; application-specific memory and
conversation workflows live in the service and router modules.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from backend.config import get_settings

settings = get_settings()
_is_sqlite = settings.database_url.startswith("sqlite")
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)

if _is_sqlite:
    @event.listens_for(Engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        """SQLite does not enforce foreign keys unless explicitly enabled."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class User(Base):
    """Local owner namespace for a user's memories and conversations."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(500), nullable=True)
    skills_initialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    memories: Mapped[list["Memory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Memory(Base):
    """Durable personal memory, separate from raw chat history."""
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional serialized embedding; MVP retrieval can begin with text matching.
    embedding_vector: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    user: Mapped[User] = relationship(back_populates="memories")


class Conversation(Base):
    """Conversation thread that can be resumed across app sessions."""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), default="New conversation", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Message.created_at"
    )


class Message(Base):
    """One user or assistant turn within a conversation."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Skill(Base):
    """A user-owned reusable workflow; execution is limited to allowlisted tools."""
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    enabled_tools: Mapped[str] = mapped_column(Text, default='["memory"]', nullable=False)
    is_template: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    user: Mapped[User] = relationship(back_populates="skills")


def init_db() -> None:
    """Create tables and apply the small additive user-column migration for existing MVP DBs."""
    Base.metadata.create_all(bind=engine)
    # create_all does not add columns to an already-existing users table.
    # These additive columns preserve any existing memories/conversations.
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as connection:
            if "email" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(320)"))
            if "password_hash" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(500)"))
            if "skills_initialized" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN skills_initialized BOOLEAN NOT NULL DEFAULT FALSE"))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
            ))


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that always closes its session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_user(db: Session, user_id: str) -> User:
    """Get or create a local user namespace."""
    normalized_id = user_id.strip()
    if not normalized_id:
        raise ValueError("user_id must not be empty")
    user = db.get(User, normalized_id)
    if user is None:
        user = User(id=normalized_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
