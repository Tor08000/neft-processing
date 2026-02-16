from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt

ALGORITHM = "HS256"
TOKEN_TYPE = "onboarding_app"
DEFAULT_EXP_DAYS = 30


class OnboardingTokenError(Exception):
    pass


def _get_secret() -> str:
    secret = os.getenv("ONBOARDING_TOKEN_SECRET") or os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("ONBOARDING_TOKEN_SECRET environment variable is required")
    return secret


def issue_application_access_token(application_id: str, scope: str = "edit") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "typ": TOKEN_TYPE,
        "app_id": application_id,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=DEFAULT_EXP_DAYS)).timestamp()),
    }
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


def verify_application_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise OnboardingTokenError("invalid_onboarding_token") from exc
    if payload.get("typ") != TOKEN_TYPE or not payload.get("app_id"):
        raise OnboardingTokenError("invalid_onboarding_token")
    return payload


def unauthorized(reason_code: str = "invalid_onboarding_token") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"reason_code": reason_code})
