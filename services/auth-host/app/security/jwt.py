from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from typing import Tuple

from jose import JWTError, jwt
from redis import Redis

import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

from jose import JWTError, jwt
from redis import Redis

from neft_shared.settings import get_settings

settings = get_settings()
ALG = "HS256"


class TokenError(Exception):
    pass


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def issue_tokens(sub: str) -> dict:
    now = _now_utc()
    acc_exp = now + timedelta(minutes=settings.access_token_expires_min)
    ref_exp = now + timedelta(days=settings.refresh_token_expires_days)
    jti = str(uuid.uuid4())
    access = jwt.encode({"sub": sub, "exp": acc_exp, "typ": "access"}, settings.jwt_secret, algorithm=ALG)
    refresh = jwt.encode(
        {"sub": sub, "exp": ref_exp, "typ": "refresh", "jti": jti}, settings.jwt_secret, algorithm=ALG
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "jti": jti,
        "refresh_exp": int(ref_exp.timestamp()),
    }


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALG])
        return payload
    except JWTError as e:
        raise TokenError(f"Invalid token: {e}")


def validate_refresh(token: str) -> Tuple[str, str, int]:
    """Возвращает (sub, jti, exp_ts). Проверяет что тип refresh."""

    payload = decode_token(token)
    if payload.get("typ") != "refresh":
        raise TokenError("Not a refresh token")
    sub = payload.get("sub")
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not sub or not jti or not exp:
        raise TokenError("Malformed refresh token")
    return sub, jti, int(exp)


# Redis helpers

def store_refresh(redis: Redis, jti: str, exp_ts: int, sub: str) -> None:
    ttl = max(1, exp_ts - int(_now_utc().timestamp()))
    # храним ключ до истечения токена
    redis.setex(f"auth:rt:{jti}", ttl, sub)


def is_refresh_active(redis: Redis, jti: str) -> bool:
    return redis.exists(f"auth:rt:{jti}") == 1


def revoke_refresh(redis: Redis, jti: str) -> None:
    redis.delete(f"auth:rt:{jti}")
