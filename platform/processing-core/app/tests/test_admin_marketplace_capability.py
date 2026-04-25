from __future__ import annotations

from uuid import uuid4

import pytest

from app.api.dependencies.admin import require_admin_user
from app.routers.admin import marketplace_catalog, marketplace_orders, marketplace_sponsored
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def _admin_token_for_roles(roles: list[str]) -> dict:
    return {
        "user_id": str(uuid4()),
        "sub": str(uuid4()),
        "email": "admin-marketplace-capability@neft.test",
        "roles": roles,
    }


@pytest.mark.parametrize(
    ("router", "method", "path", "payload"),
    [
        (marketplace_catalog.router, "get", "/api/core/v1/admin/products", None),
        (marketplace_orders.router, "get", "/api/core/v1/admin/marketplace/orders", None),
        (marketplace_sponsored.router, "get", "/api/core/v1/admin/marketplace/sponsored/campaigns", None),
    ],
)
def test_hidden_marketplace_read_surfaces_reject_non_marketplace_roles(router, method, path, payload) -> None:
    with scoped_session_context(tables=()) as session:
        with router_client_context(
            router=router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_token_for_roles(["NEFT_FINANCE"])},
        ) as client:
            response = getattr(client, method)(path, json=payload) if payload is not None else getattr(client, method)(path)

    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden_admin_role"


@pytest.mark.parametrize(
    ("router", "method", "path", "payload"),
    [
        (
            marketplace_catalog.router,
            "post",
            "/api/core/v1/admin/partners/partner-1/verify",
            {"status": "VERIFIED", "reason": "reviewed"},
        ),
        (
            marketplace_orders.router,
            "post",
            "/api/core/v1/admin/marketplace/orders/order-1/settlement-override",
            {
                "gross_amount": "100.00",
                "platform_fee": "10.00",
                "penalties": "0.00",
                "partner_net": "90.00",
                "currency": "RUB",
                "reason": "operator adjustment",
            },
        ),
        (
            marketplace_sponsored.router,
            "patch",
            "/api/core/v1/admin/marketplace/sponsored/campaigns/campaign-1/status",
            {"status": "PAUSED", "reason": "moderation hold"},
        ),
    ],
)
def test_hidden_marketplace_write_surfaces_reject_read_only_marketplace_roles(router, method, path, payload) -> None:
    with scoped_session_context(tables=()) as session:
        with router_client_context(
            router=router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_token_for_roles(["NEFT_SUPPORT"])},
        ) as client:
            response = getattr(client, method)(path, json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden_admin_role"
