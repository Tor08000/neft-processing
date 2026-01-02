from fastapi import Depends

from app.services.partner_auth import require_partner_user


def partner_portal_user(token: dict = Depends(require_partner_user)) -> dict:
    return token


__all__ = ["partner_portal_user"]
