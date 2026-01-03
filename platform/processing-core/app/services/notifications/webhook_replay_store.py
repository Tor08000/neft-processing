from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from redis import Redis
from sqlalchemy.orm import Session

from app.models.fuel import WebhookNonceRecord


class WebhookNonceStore(Protocol):
    def check_and_store(self, nonce: str, ttl_seconds: int) -> bool:
        ...


@dataclass
class RedisWebhookNonceStore:
    redis: Redis
    namespace: str = "webhook:nonce:"

    def check_and_store(self, nonce: str, ttl_seconds: int) -> bool:
        key = f"{self.namespace}{nonce}"
        return bool(self.redis.set(key, "1", nx=True, ex=ttl_seconds))


@dataclass
class PostgresWebhookNonceStore:
    db: Session

    def check_and_store(self, nonce: str, ttl_seconds: int) -> bool:
        now = datetime.now(timezone.utc)
        existing = (
            self.db.query(WebhookNonceRecord)
            .filter(WebhookNonceRecord.nonce == nonce)
            .filter(WebhookNonceRecord.expires_at > now)
            .one_or_none()
        )
        if existing:
            return False
        record = WebhookNonceRecord(nonce=nonce, expires_at=now + timedelta(seconds=ttl_seconds))
        self.db.add(record)
        self.db.flush()
        return True


def build_replay_store(redis: Redis | None, db: Session | None) -> WebhookNonceStore | None:
    if redis is not None:
        return RedisWebhookNonceStore(redis)
    if db is not None:
        return PostgresWebhookNonceStore(db)
    return None


__all__ = [
    "PostgresWebhookNonceStore",
    "RedisWebhookNonceStore",
    "WebhookNonceStore",
    "build_replay_store",
]
