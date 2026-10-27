"""Persistent memory operations with a final PII-redaction boundary."""
from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.database import Memory, ensure_user

# Redaction is deliberately applied at persistence time, including to manually
# entered memories. This is a safeguard, not a guarantee of complete PII detection.
_EMAIL_RE = re.compile(r"\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+\b", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?<![\w])(?:\+?\d{1,3}[ .()/-]?)?(?:\(?\d{2,4}\)?[ .()/-]?)?\d{3,4}[ .-]?\d{3,4}(?!\w)"
)
_STOP_WORDS = {
    "about", "after", "again", "also", "been", "being", "could", "does", "from",
    "have", "here", "into", "just", "like", "more", "most", "other", "should",
    "some", "such", "than", "that", "their", "them", "then", "there", "these",
    "they", "this", "those", "through", "under", "very", "what", "when", "where",
    "which", "while", "with", "would", "your", "you", "user", "remember",
}


def redact_pii(text: str) -> str:
    """Replace email addresses and likely phone numbers before memory storage."""
    if not text:
        return ""
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)

    def replace_phone(match: re.Match[str]) -> str:
        candidate = match.group(0)
        digits = re.sub(r"\D", "", candidate)
        # Require at least 10 digits to avoid masking years, short IDs, and dates.
        return "[REDACTED_PHONE]" if len(digits) >= 10 else candidate

    return _PHONE_RE.sub(replace_phone, redacted)


def _terms(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-zA-Z0-9_'-]{2,}", text.lower())
        if token not in _STOP_WORDS
    }


def create_memory(db: Session, user_id: str, content: str) -> Memory:
    """Persist a sanitized memory for one user. Blank content is rejected."""
    normalized = redact_pii(content).strip()
    if not normalized or normalized in {"[REDACTED_EMAIL]", "[REDACTED_PHONE]"}:
        raise ValueError("Memory must contain useful non-sensitive content after redaction.")
    if len(normalized) > 10_000:
        normalized = normalized[:10_000]
    ensure_user(db, user_id)
    memory = Memory(user_id=user_id.strip(), content=normalized)
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def list_memories(db: Session, user_id: str, *, limit: int = 100) -> list[Memory]:
    """Return newest memories for the requested user only."""
    ensure_user(db, user_id)
    safe_limit = max(1, min(int(limit), 500))
    statement = (
        select(Memory).where(Memory.user_id == user_id.strip())
        .order_by(Memory.updated_at.desc(), Memory.id.desc()).limit(safe_limit)
    )
    return list(db.scalars(statement).all())


def retrieve_relevant_memories(db: Session, user_id: str, query: str, *, limit: int = 5) -> list[Memory]:
    """Rank a user's memories by simple token overlap; no vector DB required."""
    memories = list_memories(db, user_id, limit=500)
    query_terms = _terms(query)
    if not query_terms:
        return memories[:max(1, limit)]
    ranked: list[tuple[float, int, Memory]] = []
    for memory in memories:
        memory_terms = _terms(memory.content)
        overlap = query_terms & memory_terms
        if overlap:
            score = len(overlap) / max(1, len(query_terms) ** 0.5 * len(memory_terms) ** 0.25)
            ranked.append((score, memory.id, memory))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked[:max(1, limit)]]


def format_memories(memories: Iterable[Memory]) -> str:
    lines = [memory.content.strip() for memory in memories if memory.content.strip()]
    return "Relevant saved memories (user-provided context; use only when relevant):\n- " + "\n- ".join(lines) if lines else ""


def delete_memories(db: Session, user_id: str) -> int:
    ensure_user(db, user_id)
    result = db.execute(delete(Memory).where(Memory.user_id == user_id.strip()))
    db.commit()
    return int(result.rowcount or 0)


def save_memory_candidate(db: Session, user_id: str, candidate: str) -> Memory | None:
    """Save a conservative candidate after PII filtering; reject empty/redaction-only results."""
    normalized = " ".join(redact_pii(candidate).split())
    if not normalized or normalized.upper() == "NO_MEMORY":
        return None
    if len(normalized) > 1000:
        normalized = normalized[:1000].rstrip()
    if not re.search(r"[A-Za-z]{2,}", normalized.replace("[REDACTED_EMAIL]", "").replace("[REDACTED_PHONE]", "")):
        return None
    try:
        return create_memory(db, user_id, normalized)
    except ValueError:
        return None
