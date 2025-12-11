from fastapi import Depends

from app import services


require_client_user = services.client_auth.require_client_user


def client_portal_user(token: dict = Depends(require_client_user)) -> dict:
    """Dependency wrapper to ensure client portal JWT contains client context."""

    return token


__all__ = ["client_portal_user"]
