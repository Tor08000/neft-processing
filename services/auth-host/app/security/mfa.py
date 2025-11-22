from __future__ import annotations
import pyotp
from typing import Optional
from redis import Redis

def mfa_secret_key(redis: Redis, email: str) -> str:
    key = f"auth:mfa:{email}:secret"
    s = redis.get(key)
    if s:
        return s  # type: ignore
    # создаём новый secret (base32) и храним
    secret = pyotp.random_base32()
    redis.set(key, secret)
    return secret

def mfa_get_secret(redis: Redis, email: str) -> Optional[str]:
    s = redis.get(f"auth:mfa:{email}:secret")
    return s if s else None  # type: ignore

def mfa_enabled(redis: Redis, email: str) -> bool:
    return redis.get(f"auth:mfa:{email}:enabled") in (b"1", "1", b"true", "true")

def mfa_enable(redis: Redis, email: str) -> None:
    redis.set(f"auth:mfa:{email}:enabled", 1)

def mfa_disable(redis: Redis, email: str) -> None:
    redis.delete(f"auth:mfa:{email}:enabled")

def mfa_validate_code(redis: Redis, email: str, code: str) -> bool:
    secret = mfa_get_secret(redis, email)
    if not secret:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)