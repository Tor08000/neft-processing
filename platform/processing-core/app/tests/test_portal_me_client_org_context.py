from __future__ import annotations

from uuid import uuid4

from app.models.client import Client

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table

from app.tests._scoped_router_harness import scoped_session_context
from app.services import portal_me


def test_portal_me_client_org_context_prefers_numeric_org_id_from_token() -> None:
    client_id = str(uuid4())

    resolved_client_id, org_id_raw, org_id_int = portal_me._resolve_client_org_context(
        db=None,  # type: ignore[arg-type]
        token={"client_id": client_id, "org_id": 101},
        client_id=client_id,
    )

    assert resolved_client_id == client_id
    assert org_id_raw == "101"
    assert org_id_int == 101


def test_portal_me_client_org_context_ignores_partner_only_numeric_org(monkeypatch) -> None:
    client_id = str(uuid4())
    monkeypatch.setattr(portal_me, "_org_id_has_role", lambda db, org_id, role: False)

    resolved_client_id, org_id_raw, org_id_int = portal_me._resolve_client_org_context(
        db=None,  # type: ignore[arg-type]
        token={"client_id": client_id, "org_id": 1, "portal": "client"},
        client_id=client_id,
    )

    assert resolved_client_id == client_id
    assert org_id_raw == client_id
    assert org_id_int is None


def test_portal_me_client_org_context_falls_back_to_org_lookup(monkeypatch) -> None:
    client_id = str(uuid4())
    monkeypatch.setattr(portal_me, "_resolve_org_id_from_client", lambda db, client_id: 77)

    resolved_client_id, org_id_raw, org_id_int = portal_me._resolve_client_org_context(
        db=None,  # type: ignore[arg-type]
        token={"client_id": client_id},
        client_id=client_id,
    )

    assert resolved_client_id == client_id
    assert org_id_raw == "77"
    assert org_id_int == 77


def test_portal_me_client_org_context_falls_back_to_subscription_lookup(monkeypatch) -> None:
    client_id = str(uuid4())

    class _FakeResult:
        def scalar_one_or_none(self) -> int:
            return 88

    class _FakeSession:
        def execute(self, query):
            return _FakeResult()

    subscriptions = Table(
        "client_subscriptions",
        MetaData(),
        Column("tenant_id", Integer),
        Column("client_id", String),
        Column("created_at", DateTime(timezone=True)),
    )
    monkeypatch.setattr(portal_me, "_table_exists", lambda db, name: name == "client_subscriptions")
    monkeypatch.setattr(portal_me, "_table", lambda db, name: subscriptions)

    assert portal_me._resolve_org_id_from_client_subscription(_FakeSession(), client_id=client_id) == 88


def test_portal_me_client_org_lookup_uses_subscription_when_orgs_have_no_client_link(monkeypatch) -> None:
    client_id = str(uuid4())

    orgs = Table(
        "orgs",
        MetaData(),
        Column("id", Integer),
    )
    subscriptions = Table(
        "client_subscriptions",
        MetaData(),
        Column("tenant_id", Integer),
        Column("client_id", String),
        Column("created_at", DateTime(timezone=True)),
    )

    def _table_exists(db, name: str) -> bool:
        return name in {"orgs", "client_subscriptions"}

    def _table(db, name: str):
        return orgs if name == "orgs" else subscriptions

    monkeypatch.setattr(portal_me, "_table_exists", _table_exists)
    monkeypatch.setattr(portal_me, "_table", _table)
    monkeypatch.setattr(portal_me, "_resolve_org_id_from_client_subscription", lambda db, client_id: 91)

    assert portal_me._resolve_org_id_from_client(db=None, client_id=client_id) == 91


def test_portal_me_normalize_subscription_status_strips_enum_prefix() -> None:
    assert portal_me._normalize_subscription_status("SubscriptionStatus.FREE") == "FREE"
    assert portal_me._normalize_subscription_status("ACTIVE") == "ACTIVE"


def test_client_profile_complete_accepts_individual_without_inn() -> None:
    client = Client(id=uuid4(), name="Demo Client", full_name="Demo Client", org_type="INDIVIDUAL", status="ACTIVE")

    assert (
        portal_me._is_client_profile_complete(
            client=client,
            onboarding_profile=None,
            onboarding=None,
            approved_application_org_type=None,
        )
        is True
    )


def test_client_profile_complete_keeps_business_inn_requirement() -> None:
    client = Client(id=uuid4(), name="Demo Client", legal_name="Demo Client", org_type="LEGAL", status="ACTIVE")

    assert (
        portal_me._is_client_profile_complete(
            client=client,
            onboarding_profile=None,
            onboarding=None,
            approved_application_org_type=None,
        )
        is False
    )


def test_portal_me_keeps_legacy_active_client_without_contract_in_active_state(monkeypatch) -> None:
    class _Snapshot:
        entitlements = {
            "org_roles": ["CLIENT"],
            "capabilities": ["CLIENT_CORE", "MARKETPLACE"],
            "modules": {"MARKETPLACE": {"enabled": True}},
            "subscription": {
                "plan_code": "DEMO_CONTROL_INDIVIDUAL_1M",
                "status": "ACTIVE",
                "billing_cycle": "MONTHLY",
            },
        }

    with scoped_session_context(tables=(Client.__table__,)) as session:
        client_uuid = uuid4()
        client_id = str(client_uuid)
        session.add(
            Client(
                id=client_uuid,
                name="Demo Client",
                full_name="Demo Client",
                org_type="INDIVIDUAL",
                status="ACTIVE",
            )
        )
        session.commit()

        monkeypatch.setattr(portal_me, "get_org_entitlements_snapshot", lambda db, org_id: _Snapshot())

        payload = portal_me.build_portal_me(
            session,
            token={
                "client_id": client_id,
                "org_id": 1,
                "sub": "owner-1",
                "user_id": "owner-1",
                "subject_type": "client_user",
                "portal": "client",
                "roles": ["CLIENT_OWNER"],
            },
        )

    assert payload.access_state == "ACTIVE"
    assert payload.access_reason is None
