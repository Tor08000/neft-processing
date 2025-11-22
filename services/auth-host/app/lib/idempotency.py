# services/auth-host/app/lib/idempotency.py

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis  # вместо aioredis

logger = logging.getLogger(__name__)

REDIS_DSN = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")


def get_redis() -> Redis:
    # один общий клиент на процесс
    return Redis.from_url(
        REDIS_DSN,
        decode_responses=True,
    )


_redis = get_redis()


@asynccontextmanager
async def idem_lock(key: str, ttl: int = 30) -> AsyncIterator[bool]:
    """
    Простейшая идемпотентная блокировка:
    - ставим ключ idempotency:{key} c EX=ttl и NX
    - если не смогли поставить — считаем, что уже есть активный запрос
    """
    lock_key = f"idempotency:{key}"
    acquired = False
    try:
        acquired = await _redis.set(lock_key, "1", ex=ttl, nx=True)
        yield bool(acquired)
    finally:
        if acquired:
            try:
                await _redis.delete(lock_key)
            except Exception as e:
                logger.warning("Failed to release idempotency lock %s: %s", lock_key, e)
