from __future__ import annotations

import os
import time

import httpx
from fastapi import HTTPException

AUTH_SESSION_STATUS_URL = os.getenv(
    "AUTH_SESSION_STATUS_URL",
    "http://auth-host:8000/api/v1/auth/sessions/{sid}/status",
)
SESSION_STATUS_CACHE_TTL_SECONDS = int(os.getenv("SESSION_STATUS_CACHE_TTL_SECONDS", "45"))
if os.getenv("APP_ENV", "dev").lower() == "dev":
    SESSION_STATUS_CACHE_TTL_SECONDS = max(SESSION_STATUS_CACHE_TTL_SECONDS, 10)

_cache: dict[str, tuple[float, bool]] = {}


def _cache_get(sid: str) -> bool | None:
    rec = _cache.get(sid)
    if not rec:
        return None
    ts, active = rec
    if time.time() - ts > SESSION_STATUS_CACHE_TTL_SECONDS:
        _cache.pop(sid, None)
        return None
    return active


def _cache_set(sid: str, active: bool) -> None:
    _cache[sid] = (time.time(), active)


def ensure_session_active(payload: dict) -> None:
    sid = payload.get("sid")
    if not sid:
        return

    cached = _cache_get(str(sid))
    if cached is False:
        raise HTTPException(status_code=401, detail="session_revoked")
    if cached is True:
        return

    url = AUTH_SESSION_STATUS_URL.format(sid=sid)
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(url)
    except Exception as exc:  # network fail-open
        return

    if resp.status_code == 404:
        _cache_set(str(sid), False)
        raise HTTPException(status_code=401, detail="session_not_found")

    if resp.status_code != 200:
        return

    body = resp.json()
    active = bool(body.get("active"))
    _cache_set(str(sid), active)
    if not active:
        raise HTTPException(status_code=401, detail="session_revoked")
