
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import settings

ALG = "HS256"

class TokenError(Exception):
    pass

def create_access_token(sub: str):
    exp = datetime.now(tz=timezone.utc) + timedelta(minutes=settings.access_token_expires_min)
    return jwt.encode({"sub": sub, "exp": exp}, settings.jwt_secret, algorithm=ALG)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALG])
        # простая базовая проверка
        sub = payload.get("sub")
        if not sub:
            raise TokenError("Invalid token: no subject")
        return payload
    except JWTError as e:
        raise TokenError(f"Invalid token: {e}")
