from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.admin_users import AdminUserCreateRequest, AdminUserUpdateRequest


def test_admin_user_schema_accepts_canonical_admin_roles() -> None:
    payload = AdminUserCreateRequest(
        email="admin@neft.local",
        password="secret123",
        roles=["PLATFORM_ADMIN", "NEFT_SUPPORT", "ANALYST"],
        reason="Create new admin contour",
        correlation_id="corr-admin-schema-1",
    )

    assert payload.roles == ["PLATFORM_ADMIN", "NEFT_SUPPORT", "ANALYST"]
    assert payload.reason == "Create new admin contour"
    assert payload.correlation_id == "corr-admin-schema-1"


def test_admin_user_schema_keeps_client_role_compatibility() -> None:
    payload = AdminUserUpdateRequest(roles=["CLIENT_MANAGER"], reason="Compatibility check", correlation_id="  ")

    assert payload.roles == ["CLIENT_MANAGER"]
    assert payload.reason == "Compatibility check"
    assert payload.correlation_id is None


def test_admin_user_schema_rejects_unknown_roles() -> None:
    with pytest.raises(ValidationError):
        AdminUserUpdateRequest(roles=["NOT_A_REAL_ROLE"])
