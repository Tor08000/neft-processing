from __future__ import annotations

from app.api.dependencies.admin import require_admin_user
from app.models.audit_log import ActorType, AuditLog
from app.routers.admin.audit import router as audit_router
from app.security.rbac.principal import Principal, get_principal
from app.services.audit_service import AuditService, RequestContext
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def _admin_claims(*roles: str) -> dict[str, object]:
    return {
        "user_id": "admin-audit-1",
        "sub": "admin-audit-1",
        "email": "audit-admin@neft.test",
        "roles": list(roles),
    }


def _admin_principal() -> Principal:
    return Principal(
        user_id=None,
        roles={"admin"},
        scopes=set(),
        client_id=None,
        partner_id=None,
        is_admin=True,
        raw_claims={"sub": "admin-audit-1", "roles": ["PLATFORM_ADMIN"]},
    )


def test_admin_audit_feed_supports_admin_user_entity_filters() -> None:
    with scoped_session_context(tables=(AuditLog.__table__,)) as session:
        service = AuditService(session)
        service.audit(
            event_type="ADMIN_USER_UPDATED",
            entity_type="admin_user",
            entity_id="admin-42",
            action="update",
            after={"roles": ["NEFT_SUPPORT"]},
            external_refs={"correlation_id": "corr-admin-42"},
            reason="Promote support lead",
            request_ctx=RequestContext(
                actor_type=ActorType.USER,
                actor_id="platform-admin-1",
                actor_email="platform-admin@neft.test",
                actor_roles=["PLATFORM_ADMIN"],
            ),
        )
        service.audit(
            event_type="INVOICE_MARKED_PAID",
            entity_type="billing_invoice",
            entity_id="invoice-77",
            action="mark_paid",
            after={"status": "PAID"},
            request_ctx=RequestContext(
                actor_type=ActorType.USER,
                actor_id="finance-admin-1",
                actor_email="finance-admin@neft.test",
                actor_roles=["NEFT_FINANCE"],
            ),
        )
        session.commit()

        with router_client_context(
            router=audit_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={
                require_admin_user: lambda: _admin_claims("PLATFORM_ADMIN"),
                get_principal: _admin_principal,
            },
        ) as client:
            response = client.get(
                "/api/core/v1/admin/audit",
                params={"entity_type": "admin_user", "entity_id": "admin-42"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["type"] == "ADMIN_USER_UPDATED"
    assert payload["items"][0]["entity_type"] == "admin_user"
    assert payload["items"][0]["entity_id"] == "admin-42"
    assert payload["items"][0]["actor_type"] == "USER"
    assert payload["items"][0]["correlation_id"] == "corr-admin-42"


def test_admin_audit_feed_filters_by_correlation_id() -> None:
    with scoped_session_context(tables=(AuditLog.__table__,)) as session:
        service = AuditService(session)
        service.audit(
            event_type="PARTNER_PAYOUT_APPROVED",
            entity_type="partner_payout_request",
            entity_id="payout-1",
            action="approve",
            after={"status": "APPROVED"},
            external_refs={"correlation_id": "corr-payout-1"},
            request_ctx=RequestContext(
                actor_type=ActorType.USER,
                actor_id="finance-admin-1",
                actor_email="finance-admin@neft.test",
                actor_roles=["NEFT_FINANCE"],
            ),
        )
        service.audit(
            event_type="PARTNER_PAYOUT_REQUESTED",
            entity_type="partner_payout_request",
            entity_id="payout-2",
            action="request",
            after={"status": "REQUESTED"},
            external_refs={"correlation_id": "corr-payout-2"},
            request_ctx=RequestContext(
                actor_type=ActorType.USER,
                actor_id="finance-admin-1",
                actor_email="finance-admin@neft.test",
                actor_roles=["NEFT_FINANCE"],
            ),
        )
        session.commit()

        with router_client_context(
            router=audit_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={
                require_admin_user: lambda: _admin_claims("NEFT_FINANCE"),
                get_principal: _admin_principal,
            },
        ) as client:
            feed_response = client.get(
                "/api/core/v1/admin/audit",
                params={"correlation_id": "corr-payout-1"},
            )
            chain_response = client.get("/api/core/v1/admin/audit/corr-payout-1")

    assert feed_response.status_code == 200
    feed_payload = feed_response.json()
    assert feed_payload["total"] == 1
    assert feed_payload["items"][0]["entity_id"] == "payout-1"
    assert feed_payload["items"][0]["correlation_id"] == "corr-payout-1"

    assert chain_response.status_code == 200
    chain_payload = chain_response.json()
    assert chain_payload["correlation_id"] == "corr-payout-1"
    assert len(chain_payload["items"]) == 1
    assert chain_payload["items"][0]["entity_id"] == "payout-1"
