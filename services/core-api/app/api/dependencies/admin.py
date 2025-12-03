from fastapi import Depends

from app.services.admin_auth import require_admin


def require_admin_user(token: dict = Depends(require_admin)) -> dict:
    """Dependency wrapper to validate admin JWT tokens.

    This keeps all admin-specific auth enforcement in a dedicated place so it can be
    attached to the admin router prefix without affecting public endpoints.
    """

    return token


__all__ = ["require_admin_user"]
