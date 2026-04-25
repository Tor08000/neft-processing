from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers.admin.revenue import require_revenue_access
from app.services.admin_portal_access import (
    admin_capability_allows,
    build_admin_permissions,
    primary_admin_level,
    resolve_admin_levels,
)


def test_support_admin_permissions_focus_on_cases_and_onboarding() -> None:
    permissions = build_admin_permissions(["NEFT_SUPPORT"])

    assert permissions["cases"]["read"] is True
    assert permissions["cases"]["operate"] is True
    assert permissions["cases"]["approve"] is True
    assert permissions["onboarding"]["manage"] is True
    assert permissions["commercial"]["read"] is True
    assert permissions["commercial"]["write"] is False
    assert permissions["marketplace"]["approve"] is False
    assert primary_admin_level(["NEFT_SUPPORT"]) == "support_admin"


def test_finance_admin_does_not_inherit_marketplace_or_crm_actions() -> None:
    permissions = build_admin_permissions(["NEFT_FINANCE"])

    assert permissions["finance"]["override"] is True
    assert permissions["finance"]["write"] is True
    assert permissions["revenue"]["read"] is True
    assert permissions["revenue"]["write"] is False
    assert permissions["commercial"]["read"] is True
    assert permissions["crm"]["read"] is False
    assert permissions["marketplace"]["approve"] is False
    assert admin_capability_allows(["NEFT_FINANCE"], "finance", "approve") is True
    assert admin_capability_allows(["NEFT_FINANCE"], "revenue", "read") is True
    assert admin_capability_allows(["NEFT_FINANCE"], "marketplace", "approve") is False


def test_revenue_capability_is_narrower_than_finance_read() -> None:
    assert build_admin_permissions(["NEFT_SUPPORT"])["finance"]["read"] is True
    assert build_admin_permissions(["NEFT_SUPPORT"])["revenue"]["read"] is False
    assert build_admin_permissions(["NEFT_OPS"])["finance"]["read"] is True
    assert build_admin_permissions(["NEFT_OPS"])["revenue"]["read"] is False
    assert build_admin_permissions(["NEFT_SALES"])["revenue"]["read"] is True
    assert build_admin_permissions(["PLATFORM_ADMIN"])["revenue"]["read"] is False


def test_revenue_route_dependency_uses_explicit_revenue_capability() -> None:
    finance_token = {"roles": ["NEFT_FINANCE"]}
    sales_token = {"roles": ["NEFT_SALES"]}
    superadmin_token = {"roles": ["NEFT_SUPERADMIN"]}

    assert require_revenue_access(finance_token) is finance_token
    assert require_revenue_access(sales_token) is sales_token
    assert require_revenue_access(superadmin_token) is superadmin_token

    for roles in (["NEFT_SUPPORT"], ["NEFT_OPS"], ["PLATFORM_ADMIN"], ["OBSERVER"]):
        with pytest.raises(HTTPException) as exc:
            require_revenue_access({"roles": roles})
        assert exc.value.status_code == 403
        assert exc.value.detail == "forbidden_revenue_role"


def test_platform_admin_and_superadmin_levels_are_explicit() -> None:
    assert resolve_admin_levels(["PLATFORM_ADMIN", "NEFT_FINANCE"]) == ["platform_admin", "finance_admin"]
    assert primary_admin_level(["NEFT_SUPERADMIN", "NEFT_FINANCE"]) == "superadmin"
