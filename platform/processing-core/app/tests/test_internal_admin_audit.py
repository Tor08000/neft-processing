from __future__ import annotations

from app.api.dependencies.admin import require_admin_user
from app.models.audit_log import AuditLog
from app.routers.internal.admin_audit import router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def test_internal_admin_user_audit_writes_canonical_audit_feed() -> None:
    with scoped_session_context(tables=(AuditLog.__table__,)) as session:
        with router_client_context(
            router=router,
            db_session=session,
            dependency_overrides={
                require_admin_user: lambda: {
                    "user_id": "admin-1",
                    "email": "platform-admin@neft.test",
                    "roles": ["PLATFORM_ADMIN"],
                }
            },
        ) as client:
            response = client.post(
                "/api/internal/admin/audit/users",
                headers={"x-request-id": "req-admin-audit-1"},
                json={
                    "action": "update",
                    "user_id": "user-42",
                    "reason": "Rotate admin ownership for support shift",
                    "correlation_id": "corr-admin-audit-1",
                    "before": {
                        "email": "user-42@neft.test",
                        "full_name": "Old Name",
                        "is_active": True,
                        "roles": ["ANALYST"],
                    },
                    "after": {
                        "email": "user-42@neft.test",
                        "full_name": "New Name",
                        "is_active": False,
                        "roles": ["NEFT_SUPPORT"],
                    },
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"

        record = session.query(AuditLog).filter(AuditLog.id == payload["audit_id"]).one()
        assert record.event_type == "ADMIN_USER_UPDATED"
        assert record.entity_type == "admin_user"
        assert record.entity_id == "user-42"
        assert record.action == "update"
        assert record.reason == "Rotate admin ownership for support shift"
        assert record.request_id == "req-admin-audit-1"
        assert record.actor_id == "admin-1"
        assert record.actor_email == "platform-admin@neft.test"
        assert record.actor_roles == ["PLATFORM_ADMIN"]
        assert record.external_refs["correlation_id"] == "corr-admin-audit-1"
        assert record.external_refs["source_service"] == "auth-host"
        assert record.external_refs["source_surface"] == "admin_users"
        assert record.before["roles"] == ["ANALYST"]
        assert record.after["roles"] == ["NEFT_SUPPORT"]
        assert record.diff["roles"] == {"before": ["ANALYST"], "after": ["NEFT_SUPPORT"]}


def test_internal_admin_user_audit_requires_access_management() -> None:
    with scoped_session_context(tables=(AuditLog.__table__,)) as session:
        with router_client_context(
            router=router,
            db_session=session,
            dependency_overrides={
                require_admin_user: lambda: {
                    "user_id": "observer-1",
                    "email": "observer@neft.test",
                    "roles": ["ANALYST"],
                }
            },
        ) as client:
            response = client.post(
                "/api/internal/admin/audit/users",
                json={
                    "action": "create",
                    "user_id": "user-55",
                    "after": {
                        "email": "user-55@neft.test",
                        "full_name": "Observer Target",
                        "is_active": True,
                        "roles": ["ANALYST"],
                    },
                },
            )

        assert response.status_code == 403
        assert session.query(AuditLog).count() == 0
