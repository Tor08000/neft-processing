from __future__ import annotations

from app.api.dependencies.admin import require_admin_user
from app.routers.admin.ops_runtime import router as ops_runtime_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def _admin_claims(*roles: str) -> dict[str, object]:
    return {
        "user_id": "admin-ops-1",
        "sub": "admin-ops-1",
        "email": "ops@example.com",
        "roles": list(roles),
    }


def test_admin_ops_summary_allows_operator_capability_and_returns_grounded_degraded_payload() -> None:
    with scoped_session_context(tables=()) as session:
        with router_client_context(
            router=ops_runtime_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_OPS")},
        ) as client:
            response = client.get("/api/core/v1/admin/ops/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["core"]["health"] == "ok"
    assert payload["warnings"]


def test_admin_ops_summary_denies_finance_only_admin() -> None:
    with scoped_session_context(tables=()) as session:
        with router_client_context(
            router=ops_runtime_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_FINANCE")},
        ) as client:
            response = client.get("/api/core/v1/admin/ops/summary")

    assert response.status_code == 403
    assert response.json()["detail"] == "forbidden_admin_role"
