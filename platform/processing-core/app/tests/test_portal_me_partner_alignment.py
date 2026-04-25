from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

import app.services.portal_me as portal_me_module
from app.routers.portal_me import router as portal_me_router
from app.security.rbac.principal import Principal, get_principal
from app.models.client import Client
from app.models.client_user_roles import ClientUserRole
from app.models.partner import Partner
from app.models.partner_legal import PartnerLegalDetails
from app.models.partner_management import PartnerUserRole
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


def test_resolve_actor_type_honors_client_portal_over_mixed_org_roles() -> None:
    actor_type = portal_me_module._resolve_actor_type(
        {
            "portal": "client",
            "subject_type": "client_user",
            "roles": ["CLIENT_OWNER"],
        },
        ["CLIENT", "PARTNER"],
    )

    assert actor_type == "client"


def test_portal_me_resolves_client_actor_from_user_role_binding() -> None:
    client_uuid = uuid4()
    client_id = str(client_uuid)

    def _override_principal() -> Principal:
        return Principal(
            user_id=uuid4(),
            roles={"client_owner"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=False,
            raw_claims={
                "sub": "client@neft.local",
                "user_id": "client-owner-1",
                "portal": "client",
                "subject_type": "client_user",
                "roles": ["CLIENT_OWNER"],
            },
        )

    with scoped_session_context(tables=(Client.__table__, ClientUserRole.__table__)) as session:
        assert isinstance(session, Session)
        session.add(
            Client(
                id=client_uuid,
                name="Client Portal LLC",
                inn="7700000001",
                org_type="INDIVIDUAL",
                status="ACTIVE",
            )
        )
        session.add(
            ClientUserRole(
                client_id=client_uuid,
                user_id="client-owner-1",
                roles=["CLIENT_OWNER"],
            )
        )
        session.commit()

        with router_client_context(
            router=portal_me_router,
            prefix="/api/core",
            db_session=session,
            dependency_overrides={get_principal: _override_principal},
        ) as client:
            response = client.get("/api/core/portal/me")

        assert response.status_code == 200
        payload = response.json()
        assert payload["actor_type"] == "client"
        assert payload["context"] == "client"
        assert payload["org"]["id"] == client_id
        assert payload["org"]["org_type"] == "INDIVIDUAL"
        assert payload["partner"] is None
        assert payload["memberships"] == ["CLIENT"]
        assert payload["user_roles"] == ["CLIENT_OWNER"]


def test_portal_me_partner_payload_includes_kind_workspace_and_sub_role() -> None:
    partner_id = str(uuid4())

    def _override_principal() -> Principal:
        return Principal(
            user_id=uuid4(),
            roles={"partner_user"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=False,
            raw_claims={
                "sub": "finance-partner@example.com",
                "user_id": "finance-user-1",
                "partner_id": partner_id,
                "subject_type": "partner_user",
                "roles": ["PARTNER_ACCOUNTANT"],
                "entitlements_snapshot": {
                    "org_roles": ["PARTNER"],
                    "capabilities": [
                        "PARTNER_FINANCE_VIEW",
                        "PARTNER_PAYOUT_REQUEST",
                        "PARTNER_SETTLEMENTS",
                        "PARTNER_DOCUMENTS_LIST",
                    ],
                },
            },
        )

    with scoped_session_context(tables=(Partner.__table__, PartnerUserRole.__table__)) as session:
        assert isinstance(session, Session)
        session.add(
            Partner(
                id=partner_id,
                code="finance-partner",
                legal_name="Finance Partner LLC",
                partner_type="OTHER",
                status="ACTIVE",
                contacts={},
            )
        )
        session.add(
            PartnerUserRole(
                partner_id=partner_id,
                user_id="finance-user-1",
                roles=["PARTNER_ACCOUNTANT"],
            )
        )
        session.commit()

        with router_client_context(
            router=portal_me_router,
            prefix="/api/core",
            db_session=session,
            dependency_overrides={get_principal: _override_principal},
        ) as client:
            response = client.get("/api/core/portal/me")

        assert response.status_code == 200
        payload = response.json()
        assert payload["actor_type"] == "partner"
        assert payload["user_roles"] == ["PARTNER_ACCOUNTANT"]
        assert payload["partner"]["partner_id"] == partner_id
        assert payload["partner"]["kind"] == "FINANCE_PARTNER"
        assert payload["partner"]["partner_role"] == "FINANCE_MANAGER"
        assert payload["partner"]["partner_roles"] == ["FINANCE_MANAGER"]
        assert payload["partner"]["default_route"] == "/finance"
        assert payload["partner"]["workspaces"] == [
            {"code": "finance", "label": "Finance", "default_route": "/finance"},
            {"code": "support", "label": "Support", "default_route": "/support/requests"},
            {"code": "profile", "label": "Profile", "default_route": "/partner/profile"},
        ]


def test_portal_me_keeps_partner_actor_for_partner_portal_token_with_mixed_org_roles() -> None:
    partner_id = str(uuid4())

    def _override_principal() -> Principal:
        return Principal(
            user_id=uuid4(),
            roles={"partner_user"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=False,
            raw_claims={
                "sub": "owner@example.com",
                "user_id": "partner-owner-1",
                "portal": "partner",
                "subject_type": "partner_user",
                "roles": ["PARTNER_OWNER"],
                "partner_id": partner_id,
                "entitlements_snapshot": {
                    "org_roles": ["CLIENT", "PARTNER"],
                    "capabilities": ["PARTNER_CORE"],
                },
            },
        )

    original_table_exists = portal_me_module._table_exists

    def _table_exists_override(db, name: str) -> bool:
        if name in {"partners", "partner_user_roles"}:
            return True
        return original_table_exists(db, name)

    portal_me_module._table_exists = _table_exists_override
    try:
        with scoped_session_context(tables=(Partner.__table__, PartnerUserRole.__table__)) as session:
            assert isinstance(session, Session)
            session.add(
                Partner(
                    id=partner_id,
                    code="pending-partner",
                    legal_name="Pending Partner LLC",
                    partner_type="OTHER",
                    status="PENDING",
                    contacts={},
                )
            )
            session.add(
                PartnerUserRole(
                    partner_id=partner_id,
                    user_id="partner-owner-1",
                    roles=["PARTNER_OWNER"],
                )
            )
            session.commit()

            with router_client_context(
                router=portal_me_router,
                prefix="/api/core",
                db_session=session,
                dependency_overrides={get_principal: _override_principal},
            ) as client:
                response = client.get("/api/core/portal/me")

            assert response.status_code == 200
            payload = response.json()
            assert payload["actor_type"] == "partner"
            assert payload["user"]["subject_type"] == "partner_user"
            assert payload["partner"]["partner_id"] == partner_id
            assert payload["access_state"] == "NEEDS_ONBOARDING"
            assert payload["access_reason"] == "partner_onboarding"
    finally:
        portal_me_module._table_exists = original_table_exists


def test_portal_me_ignores_client_entitlements_leak_for_partner_actor() -> None:
    partner_id = str(uuid4())

    class _Snapshot:
        def __init__(self) -> None:
            self.entitlements = {
                "org_roles": ["CLIENT"],
                "capabilities": ["CLIENT_CORE", "CLIENT_ANALYTICS"],
                "subscription": {"plan_code": "CONTROL_INDIVIDUAL_1M", "status": "ACTIVE"},
                "org_id": 1,
            }

    def _override_principal() -> Principal:
        return Principal(
            user_id=uuid4(),
            roles={"partner_user"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=False,
            raw_claims={
                "sub": "partner@neft.local",
                "user_id": "partner-owner-1",
                "portal": "partner",
                "subject_type": "partner_user",
                "roles": ["PARTNER_OWNER"],
                "org_id": "1",
            },
        )

    original_table_exists = portal_me_module._table_exists
    original_entitlements = portal_me_module.get_org_entitlements_snapshot

    def _table_exists_override(db, name: str) -> bool:
        if name in {"partners", "partner_user_roles"}:
            return True
        return original_table_exists(db, name)

    portal_me_module._table_exists = _table_exists_override
    portal_me_module.get_org_entitlements_snapshot = lambda db, org_id: _Snapshot()
    try:
        with scoped_session_context(tables=(Partner.__table__, PartnerUserRole.__table__)) as session:
            assert isinstance(session, Session)
            session.add(
                Partner(
                    id=partner_id,
                    code="partner-client-leak",
                    legal_name="Partner Leak LLC",
                    partner_type="OTHER",
                    status="PENDING",
                    contacts={},
                )
            )
            session.add(
                PartnerUserRole(
                    partner_id=partner_id,
                    user_id="partner-owner-1",
                    roles=["PARTNER_OWNER"],
                )
            )
            session.commit()

            with router_client_context(
                router=portal_me_router,
                prefix="/api/core",
                db_session=session,
                dependency_overrides={get_principal: _override_principal},
            ) as client:
                response = client.get("/api/core/portal/me")

            assert response.status_code == 200
            payload = response.json()
            assert payload["actor_type"] == "partner"
            assert payload["partner"]["partner_id"] == partner_id
            assert payload["partner"]["status"] == "PENDING"
            assert payload["access_state"] == "NEEDS_ONBOARDING"
            assert payload["access_reason"] == "partner_onboarding"
            assert payload["capabilities"] == []
        assert payload["subscription"] is None
    finally:
        portal_me_module._table_exists = original_table_exists
        portal_me_module.get_org_entitlements_snapshot = original_entitlements


def test_portal_me_active_partner_stays_active_with_empty_partner_entitlements() -> None:
    partner_id = str(uuid4())

    class _Snapshot:
        def __init__(self) -> None:
            self.entitlements = {
                "org_roles": ["CLIENT"],
                "capabilities": ["CLIENT_CORE"],
                "subscription": {"plan_code": "CONTROL_INDIVIDUAL_1M", "status": "ACTIVE"},
                "org_id": 1,
            }

    def _override_principal() -> Principal:
        return Principal(
            user_id=uuid4(),
            roles={"partner_user"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=False,
            raw_claims={
                "sub": "partner@neft.local",
                "user_id": "partner-owner-1",
                "portal": "partner",
                "subject_type": "partner_user",
                "roles": ["PARTNER_OWNER"],
                "org_id": "1",
            },
        )

    original_table_exists = portal_me_module._table_exists
    original_entitlements = portal_me_module.get_org_entitlements_snapshot

    def _table_exists_override(db, name: str) -> bool:
        if name in {"partners", "partner_user_roles"}:
            return True
        return original_table_exists(db, name)

    portal_me_module._table_exists = _table_exists_override
    portal_me_module.get_org_entitlements_snapshot = lambda db, org_id: _Snapshot()
    try:
        with scoped_session_context(tables=(Partner.__table__, PartnerUserRole.__table__)) as session:
            assert isinstance(session, Session)
            session.add(
                Partner(
                    id=partner_id,
                    code="partner-active-empty-entitlements",
                    legal_name="Partner Active LLC",
                    partner_type="OTHER",
                    status="ACTIVE",
                    contacts={},
                )
            )
            session.add(
                PartnerUserRole(
                    partner_id=partner_id,
                    user_id="partner-owner-1",
                    roles=["PARTNER_OWNER"],
                )
            )
            session.commit()

            with router_client_context(
                router=portal_me_router,
                prefix="/api/core",
                db_session=session,
                dependency_overrides={get_principal: _override_principal},
            ) as client:
                response = client.get("/api/core/portal/me")

            assert response.status_code == 200
            payload = response.json()
            assert payload["actor_type"] == "partner"
            assert payload["partner"]["partner_id"] == partner_id
            assert payload["partner"]["status"] == "ACTIVE"
            assert payload["capabilities"] == []
            assert payload["subscription"] is None
            assert payload["access_state"] == "ACTIVE"
            assert payload["access_reason"] is None
    finally:
        portal_me_module._table_exists = original_table_exists
        portal_me_module.get_org_entitlements_snapshot = original_entitlements


def test_portal_me_falls_back_when_partner_profile_enrichment_fails() -> None:
    partner_id = str(uuid4())

    class _Snapshot:
        def __init__(self) -> None:
            self.entitlements = {
                "org_roles": ["PARTNER"],
                "capabilities": ["PARTNER_CORE"],
                "org_id": 1,
            }

    def _override_principal() -> Principal:
        return Principal(
            user_id=uuid4(),
            roles={"partner_user"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=False,
            raw_claims={
                "sub": "partner@neft.local",
                "user_id": "partner-owner-1",
                "portal": "partner",
                "subject_type": "partner_user",
                "roles": ["PARTNER_OWNER"],
                "org_id": "1",
                "partner_id": partner_id,
            },
        )

    original_table_exists = portal_me_module._table_exists
    original_entitlements = portal_me_module.get_org_entitlements_snapshot
    original_ensure_partner_profile = portal_me_module.ensure_partner_profile

    def _table_exists_override(db, name: str) -> bool:
        if name in {"partners", "partner_user_roles", "partner_profiles"}:
            return True
        return original_table_exists(db, name)

    portal_me_module._table_exists = _table_exists_override
    portal_me_module.get_org_entitlements_snapshot = lambda db, org_id: _Snapshot()

    def _raising_partner_profile(*args, **kwargs):
        raise RuntimeError("partner_profile_enrichment_failed")

    portal_me_module.ensure_partner_profile = _raising_partner_profile
    try:
        with scoped_session_context(tables=(Partner.__table__, PartnerUserRole.__table__)) as session:
            assert isinstance(session, Session)
            session.add(
                Partner(
                    id=partner_id,
                    code="partner-fallback",
                    legal_name="Partner Fallback LLC",
                    partner_type="OTHER",
                    status="ACTIVE",
                    contacts={},
                )
            )
            session.add(
                PartnerUserRole(
                    partner_id=partner_id,
                    user_id="partner-owner-1",
                    roles=["PARTNER_OWNER"],
                )
            )
            session.commit()

            with router_client_context(
                router=portal_me_router,
                prefix="/api/core",
                db_session=session,
                dependency_overrides={get_principal: _override_principal},
            ) as client:
                response = client.get("/api/core/portal/me")

            assert response.status_code == 200
            payload = response.json()
            assert payload["actor_type"] == "partner"
            assert payload["partner"]["partner_id"] == partner_id
            assert payload["partner"]["status"] == "ACTIVE"
            assert payload["access_state"] == "ACTIVE"
    finally:
        portal_me_module._table_exists = original_table_exists
        portal_me_module.get_org_entitlements_snapshot = original_entitlements
        portal_me_module.ensure_partner_profile = original_ensure_partner_profile


def test_portal_me_recovers_partner_finance_capabilities_from_numeric_alias() -> None:
    partner_id = str(uuid4())

    class _Snapshot:
        def __init__(self, org_id: int) -> None:
            if org_id == 1:
                self.entitlements = {
                    "org_id": 1,
                    "org_roles": ["PARTNER"],
                    "capabilities": [
                        "PARTNER_FINANCE_VIEW",
                        "PARTNER_PAYOUT_REQUEST",
                        "PARTNER_SETTLEMENTS",
                        "PARTNER_DOCUMENTS_LIST",
                    ],
                }
            else:
                self.entitlements = {
                    "org_id": org_id,
                    "org_roles": [],
                    "capabilities": [],
                }

    def _override_principal() -> Principal:
        return Principal(
            user_id=uuid4(),
            roles={"partner_user"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=False,
            raw_claims={
                "sub": "finance.partner@example.com",
                "user_id": "finance-partner-1",
                "portal": "partner",
                "subject_type": "partner_user",
                "roles": ["PARTNER_ACCOUNTANT"],
                "partner_id": partner_id,
                "org_id": partner_id,
            },
        )

    original_entitlements = portal_me_module.get_org_entitlements_snapshot
    portal_me_module.get_org_entitlements_snapshot = lambda db, org_id: _Snapshot(org_id)
    try:
        with scoped_session_context(
            tables=(Partner.__table__, PartnerUserRole.__table__, PartnerLegalDetails.__table__)
        ) as session:
            assert isinstance(session, Session)
            session.add(
                Partner(
                    id=partner_id,
                    code="finance-alias-partner",
                    legal_name="Finance Alias LLC",
                    partner_type="OTHER",
                    status="ACTIVE",
                    contacts={},
                )
            )
            session.add(
                PartnerUserRole(
                    partner_id=partner_id,
                    user_id="finance-partner-1",
                    roles=["PARTNER_ACCOUNTANT"],
                )
            )
            session.add(
                PartnerLegalDetails(
                    partner_id=partner_id,
                    legal_name="Finance Alias LLC",
                    inn="7700000000",
                )
            )
            session.add(
                PartnerLegalDetails(
                    partner_id="1",
                    legal_name="Finance Alias LLC",
                    inn="7700000000",
                )
            )
            session.commit()

            with router_client_context(
                router=portal_me_router,
                prefix="/api/core",
                db_session=session,
                dependency_overrides={get_principal: _override_principal},
            ) as client:
                response = client.get("/api/core/portal/me")

            assert response.status_code == 200
            payload = response.json()
            assert payload["actor_type"] == "partner"
            assert payload["entitlements_snapshot"]["org_id"] == 1
            assert "PARTNER_FINANCE_VIEW" in payload["capabilities"]
            assert payload["partner"]["default_route"] == "/finance"
            assert payload["partner"]["kind"] == "FINANCE_PARTNER"
    finally:
        portal_me_module.get_org_entitlements_snapshot = original_entitlements
