from __future__ import annotations

from fastapi import Depends

from app.services.portal_auth import require_portal_user


def portal_user(token: dict = Depends(require_portal_user)) -> dict:
    return token


__all__ = ["portal_user"]
