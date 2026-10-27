"""Small dependency-light password and bearer-token helpers for Mnemos."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from backend.config import get_settings

PBKDF2_ROUNDS = 310_000
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7


class AuthError(ValueError):
    """Invalid credentials or bearer token."""


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, rounds_text, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_text)
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: str, *, now: int | None = None) -> str:
    issued = int(time.time() if now is None else now)
    payload = {"sub": user_id, "iat": issued, "exp": issued + TOKEN_TTL_SECONDS}
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    secret = get_settings().auth_secret.encode("utf-8")
    signature = _b64(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_access_token(token: str, *, now: int | None = None) -> dict[str, Any]:
    try:
        body, supplied_signature = token.split(".", 1)
        secret = get_settings().auth_secret.encode("utf-8")
        expected_signature = _b64(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise AuthError("Invalid access token.")
        payload = json.loads(_unb64(body))
        current = int(time.time() if now is None else now)
        if not isinstance(payload.get("sub"), str) or not payload["sub"]:
            raise AuthError("Invalid access token.")
        if int(payload.get("exp", 0)) <= current:
            raise AuthError("Access token has expired. Please sign in again.")
        return payload
    except AuthError:
        raise
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise AuthError("Invalid access token.") from exc
