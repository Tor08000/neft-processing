from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import HTTPException, Request
from jose import jwt


@dataclass
class Principal:
    user_id: str
    tenant_id: str
    roles: set[str]
    subordinate_ids: set[str]


JWT_SECRET = os.getenv("CRM_JWT_SECRET", "")
JWT_ALGO = os.getenv("CRM_JWT_ALGORITHM", "HS256")


def _decode_token(token: str) -> dict:
    try:
        if JWT_SECRET:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return jwt.get_unverified_claims(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def get_principal(request: Request) -> Principal:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    claims = _decode_token(auth_header.split(" ", 1)[1])
    tenant_id = str(claims.get("tenant_id") or "")
    user_id = str(claims.get("sub") or claims.get("user_id") or "")
    if not tenant_id or not user_id:
        raise HTTPException(status_code=401, detail="Token must include tenant_id and sub")
    raw_roles = claims.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    roles = {str(role).lower() for role in raw_roles}
    subordinate_ids = {str(item) for item in (claims.get("subordinate_ids") or [])}
    return Principal(user_id=user_id, tenant_id=tenant_id, roles=roles, subordinate_ids=subordinate_ids)
