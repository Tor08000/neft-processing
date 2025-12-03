"""Wrapper for client auth dependencies.

All client-portal endpoints should rely on :func:`app.services.client_auth.require_client_user`
to validate the ``Authorization: Bearer`` header for client users.
"""

from app.services.client_auth import get_public_key, require_client_user, verify_client_token

__all__ = ["get_public_key", "require_client_user", "verify_client_token"]

