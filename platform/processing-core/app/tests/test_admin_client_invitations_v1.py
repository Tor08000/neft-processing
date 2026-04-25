from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.api.dependencies.admin import require_admin_user
from app.models.client import Client
from app.models.client_invitations import ClientInvitation
from app.routers.admin.client_invitations import router as client_invitations_router
from app.tests._scoped_router_harness import (
    ADMIN_CLIENT_INVITATION_TEST_TABLES,
    router_client_context,
    scoped_session_context,
)


def _admin_claims(*roles: str) -> dict[str, object]:
    return {
        "user_id": "admin-1",
        "sub": "admin-1",
        "email": "admin@example.com",
        "roles": list(roles),
    }


def test_admin_client_invitations_global_inbox_uses_canonical_onboarding_owner() -> None:
    with scoped_session_context(tables=ADMIN_CLIENT_INVITATION_TEST_TABLES) as session:
        client_a_id = uuid4()
        client_b_id = uuid4()
        now = datetime.now(timezone.utc)

        session.add_all(
            [
                Client(id=client_a_id, name="Acme Fleet", email="acme@example.com"),
                Client(id=client_b_id, name="Beta Route", email="beta@example.com"),
                ClientInvitation(
                    id=str(uuid4()),
                    client_id=str(client_a_id),
                    email="alpha.manager@example.com",
                    invited_by_user_id="owner-a",
                    created_by_user_id="owner-a",
                    roles=["CLIENT_MANAGER"],
                    token_hash="hash-alpha",
                    expires_at=now + timedelta(days=7),
                    status="PENDING",
                    resent_count=1,
                    last_sent_at=now,
                ),
                ClientInvitation(
                    id=str(uuid4()),
                    client_id=str(client_b_id),
                    email="beta.owner@example.com",
                    invited_by_user_id="owner-b",
                    created_by_user_id="owner-b",
                    roles=["CLIENT_OWNER"],
                    token_hash="hash-beta",
                    expires_at=now - timedelta(days=1),
                    status="PENDING",
                ),
            ]
        )
        session.commit()

        with router_client_context(
            router=client_invitations_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_SUPPORT")},
        ) as client:
            response = client.get("/api/core/v1/admin/clients/invitations", params={"status": "ALL"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 2
        emails = {item["email"] for item in payload["items"]}
        assert emails == {"alpha.manager@example.com", "beta.owner@example.com"}
        statuses = {item["email"]: item["status"] for item in payload["items"]}
        assert statuses["beta.owner@example.com"] == "EXPIRED"


def test_admin_client_invitations_global_inbox_denies_finance_only_admin() -> None:
    with scoped_session_context(tables=ADMIN_CLIENT_INVITATION_TEST_TABLES) as session:
        with router_client_context(
            router=client_invitations_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_FINANCE")},
        ) as client:
            response = client.get("/api/core/v1/admin/clients/invitations")

        assert response.status_code == 403
        assert response.json()["detail"] == "forbidden_admin_role"
