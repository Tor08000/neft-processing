from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.orm import Session

_LOCAL_LOCKS: dict[int, threading.Lock] = {}


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
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _try_pg_lock(session: Session, token: int) -> bool:
    """Attempt to take a PostgreSQL advisory transaction lock."""

    try:
        dialect = getattr(session.bind, "dialect", None)
        if not dialect or dialect.name != "postgresql":
            return False
    except Exception:
        return False

    try:
        result = session.execute(text("SELECT pg_try_advisory_xact_lock(:token)"), {"token": token}).scalar()
        return bool(result)
    except Exception:
        return False


@contextmanager
def advisory_lock(session: Session, token: int):
    """
    Attempt a non-blocking advisory lock.

    Returns True if the lock was acquired and False otherwise. For non-Postgres
    engines a local in-process lock is used to keep tests deterministic.
    """

    acquired = _try_pg_lock(session, token)
    local_lock = None

    if not acquired:
        local_lock = _LOCAL_LOCKS.setdefault(token, threading.Lock())
        acquired = local_lock.acquire(blocking=False)

    try:
        yield acquired
    finally:
        if local_lock and acquired:
            local_lock.release()
