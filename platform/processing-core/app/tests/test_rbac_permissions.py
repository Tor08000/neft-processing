from __future__ import annotations

from uuid import uuid4

from app.security.rbac.permissions import Permission
from app.security.rbac.policy import has_permission
from app.security.rbac.principal import Principal


def _principal_with_roles(*roles: str) -> Principal:
    return Principal(
        user_id=uuid4(),
        roles=set(roles),
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin="admin" in roles,
        raw_claims={},
    )


def test_client_role_permissions() -> None:
    principal = _principal_with_roles("client_user")

    assert has_permission(principal, Permission.CLIENT_INVOICES_VIEW.value)
    assert has_permission(principal, Permission.CLIENT_CONTRACTS_LIST.value)
    assert not has_permission(principal, Permission.PARTNER_SETTLEMENTS_VIEW.value)


def test_partner_role_permissions() -> None:
    principal = _principal_with_roles("partner_user")

    assert has_permission(principal, Permission.PARTNER_SETTLEMENTS_LIST.value)
    assert not has_permission(principal, Permission.PARTNER_PAYOUTS_CONFIRM.value)


def test_admin_permissions_are_global_for_known_permissions() -> None:
    principal = _principal_with_roles("admin")

    assert has_permission(principal, Permission.CLIENT_DASHBOARD_VIEW.value)
    assert has_permission(principal, Permission.ADMIN_BILLING_ALL.value)


def test_fail_closed_for_unknown_permission() -> None:
    principal = _principal_with_roles("admin")

    assert not has_permission(principal, "client:unknown:action")
