"""Compat wrapper that re-exports admin auth dependency in one place.

All admin endpoints should rely on :func:`app.services.admin_auth.require_admin` to
validate the ``Authorization: Bearer`` header and enforce the ADMIN role. This module
keeps the public import path stable while delegating to the single implementation.
"""

from app.services.admin_auth import get_public_key, require_admin, verify_admin_token

__all__ = ["get_public_key", "require_admin", "verify_admin_token"]
