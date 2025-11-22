from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from app.db import get_conn
from app.models import User

settings = get_settings()
logger = get_logger(__name__)
ALGORITHM = "HS256"
security_scheme = HTTPBearer(auto_error=False)


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", f"{password}{settings.password_pepper}".encode(), salt, 100_000
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    recalculated = hash_password(password, salt=bytes.fromhex(salt_hex))
    return hmac.compare_digest(recalculated.split("$", 1)[1], digest_hex)


def create_access_token(sub: str) -> str:
    expire = _now_utc() + timedelta(minutes=settings.access_token_expires_min)
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        logger.warning("JWT decode failed", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    payload = decode_access_token(credentials.credentials)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    async with get_conn() as (_, cur):
        await cur.execute(
            "SELECT id, email, full_name, password_hash, is_active, created_at FROM users WHERE email=%s",
            (email,),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

        user = User.from_row(row)
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_inactive")
        return user
