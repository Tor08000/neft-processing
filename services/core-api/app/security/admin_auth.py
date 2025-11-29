import time
from typing import Optional

import requests
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, ExpiredSignatureError, jwt
from sqlalchemy.orm import Session

from app.db import get_db

PUBLIC_KEY_URL = "http://auth-host:8000/.well-known/public-key"
PUBLIC_KEY_CACHE_TTL = 300

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

_cached_public_key: Optional[str] = None
_public_key_cached_at: float = 0.0


def get_public_key() -> str:
    global _cached_public_key, _public_key_cached_at

    now = time.time()
    if _cached_public_key and now - _public_key_cached_at < PUBLIC_KEY_CACHE_TTL:
        return _cached_public_key

    try:
        response = requests.get(PUBLIC_KEY_URL, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise HTTPException(status_code=503, detail="Unable to fetch public key") from exc

    _cached_public_key = response.text
    _public_key_cached_at = now
    return _cached_public_key


def verify_jwt(token: str) -> dict:
    public_key = get_public_key()
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=403, detail="Admin access required")

    role = payload.get("role")
    sub = payload.get("sub")

    if not sub or role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")

    return payload


def require_admin(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> dict:
    del db  # currently unused, but kept for future audit/logging needs
    return verify_jwt(token)
