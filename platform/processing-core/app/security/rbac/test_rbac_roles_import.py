from __future__ import annotations


def test_rbac_roles_import_smoke() -> None:
    from app.security.rbac import permissions, roles

    assert hasattr(permissions.Permission, "PARTNER_MARKETPLACE_SPONSORED_ALL")
    assert hasattr(permissions.Permission, "PARTNER_MARKETPLACE_PROMOTIONS_ALL")
    assert "partner_admin" in roles.ROLE_PERMISSIONS
