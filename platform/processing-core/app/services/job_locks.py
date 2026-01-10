from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

_LOCAL_LOCKS: dict[int, threading.Lock] = {}


def to_signed_int64(value: int) -> int:
    value &= (1 << 64) - 1
    return value - (1 << 64) if value >= (1 << 63) else value


def make_stable_key(job_type: str, scope: Mapping[str, Any], provided: str | None = None) -> str:
    """
    Build a deterministic idempotency key for the given job scope.

    The same payload produces the same key across restarts. Ordering of the
    scope dictionary does not matter.
    """

    if provided:
        return provided

    serialized_scope = json.dumps(scope, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(f"{job_type}:{serialized_scope}".encode())
    return digest.hexdigest()


def make_lock_token(job_type: str, scope_key: str) -> int:
    """Generate a 64-bit integer token suitable for Postgres advisory locks."""

    digest = hashlib.sha256(f"{job_type}:{scope_key}".encode()).digest()
    token = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return to_signed_int64(token)


def _try_pg_lock(session: Session, token: int) -> bool:
    """Attempt to take a PostgreSQL advisory transaction lock."""

    dialect = getattr(session.bind, "dialect", None)
    if not dialect or dialect.name != "postgresql":
        return False

    try:
        result = session.execute(
            text("SELECT pg_try_advisory_xact_lock(CAST(:token AS BIGINT))"),
            {"token": token},
        ).scalar()
        return bool(result)
    except (DBAPIError, SQLAlchemyError):
        session.rollback()
        raise


@contextmanager
def advisory_lock(session: Session, token: int):
    """
    Attempt a non-blocking advisory lock.

    Returns True if the lock was acquired and False otherwise. For non-Postgres
    engines a local in-process lock is used to keep tests deterministic.
    """

    signed_token = to_signed_int64(token)
    try:
        acquired = _try_pg_lock(session, signed_token)
    except (DBAPIError, SQLAlchemyError):
        session.rollback()
        raise
    local_lock = None

    if not acquired:
        local_lock = _LOCAL_LOCKS.setdefault(signed_token, threading.Lock())
        acquired = local_lock.acquire(blocking=False)

    try:
        yield acquired
    finally:
        if local_lock and acquired:
            local_lock.release()
