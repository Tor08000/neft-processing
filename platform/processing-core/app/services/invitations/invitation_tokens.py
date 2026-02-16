from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256


def generate_invitation_token() -> tuple[str, str]:
    token_raw = secrets.token_urlsafe(32)
    pepper = os.getenv("CLIENT_INVITATION_TOKEN_PEPPER", "")
    token_hash = sha256(f"{token_raw}{pepper}".encode("utf-8")).hexdigest()
    return token_raw, token_hash


def hash_invitation_token(token: str) -> str:
    pepper = os.getenv("CLIENT_INVITATION_TOKEN_PEPPER", "")
    return sha256(f"{token}{pepper}".encode("utf-8")).hexdigest()


def invite_ttl_minutes() -> int:
    return max(int(os.getenv("INVITE_TOKEN_TTL_MINUTES", "1440")), 1)


def invite_expiration(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current + timedelta(minutes=invite_ttl_minutes())
