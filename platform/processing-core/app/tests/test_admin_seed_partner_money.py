from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.partner import Partner
from app.models.partner_finance import PartnerAccount, PartnerPayoutRequest, PartnerPayoutRequestStatus
from app.models.partner_management import PartnerUserRole
from app.models.partner_legal import PartnerLegalDetails, PartnerLegalProfile
from app.models.settlement_v1 import SettlementPeriod
from app.routers.admin import seed_partner_money
from app.services.entitlements_v2_service import get_org_entitlements_snapshot


def _make_client() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    Partner.__table__.create(bind=engine)
    PartnerAccount.__table__.create(bind=engine)
    PartnerUserRole.__table__.create(bind=engine)
    PartnerLegalDetails.__table__.create(bind=engine)
    PartnerLegalProfile.__table__.create(bind=engine)
    PartnerPayoutRequest.__table__.create(bind=engine)
    SettlementPeriod.__table__.create(bind=engine)

    metadata = MetaData()
    orgs = Table(
        "orgs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(255), nullable=True),
        Column("status", String(32), nullable=True),
        Column("roles", JSON, nullable=True),
    )
    subscription_plans = Table(
        "subscription_plans",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("code", String(64), nullable=False),
        Column("version", Integer, nullable=True),
    )
    org_subscriptions = Table(
        "org_subscriptions",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("org_id", Integer, nullable=False),
        Column("plan_id", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("billing_cycle", String(32), nullable=True),
    )
    subscription_plan_features = Table(
        "subscription_plan_features",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("plan_id", String(64), nullable=False),
        Column("feature_key", String(128), nullable=False),
        Column("availability", String(32), nullable=False),
        Column("limits_json", JSON, nullable=True),
    )
    subscription_plan_modules = Table(
        "subscription_plan_modules",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("plan_id", String(64), nullable=False),
        Column("module_code", String(64), nullable=False),
        Column("enabled", Integer, nullable=False, default=1),
        Column("tier", String(32), nullable=True),
        Column("limits_json", JSON, nullable=True),
    )
    org_subscription_addons = Table(
        "org_subscription_addons",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("org_subscription_id", Integer, nullable=False),
        Column("addon_id", Integer, nullable=False),
        Column("status", String(32), nullable=False),
    )
    addons = Table(
        "addons",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("code", String(64), nullable=False),
    )
    org_subscription_overrides = Table(
        "org_subscription_overrides",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("org_subscription_id", Integer, nullable=False),
        Column("feature_key", String(128), nullable=False),
        Column("availability", String(32), nullable=False),
        Column("limits_json", JSON, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=True),
        Column("updated_at", DateTime(timezone=True), nullable=True),
    )
    support_plans = Table(
        "support_plans",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("code", String(64), nullable=False),
    )
    slo_tiers = Table(
        "slo_tiers",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("code", String(64), nullable=False),
    )
    org_entitlements_snapshot = Table(
        "org_entitlements_snapshot",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("org_id", Integer, nullable=False),
        Column("subscription_id", Integer, nullable=True),
        Column("entitlements_json", JSON, nullable=False),
        Column("hash", String(128), nullable=False),
        Column("version", Integer, nullable=False),
        Column("computed_at", DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(seed_partner_money.router, prefix="/api/core/v1/admin")
    app.state.testing_session_local = testing_session_local

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_user] = lambda: {"user_id": "admin-1", "role": "admin"}
    with testing_session_local() as db:
        db.execute(orgs.insert().values(id=1, name="demo-client", status="ACTIVE", roles=["CLIENT"]))
        db.execute(subscription_plans.insert().values(id="plan-1", code="CONTROL_INDIVIDUAL_1M", version=1))
        db.execute(
            org_subscriptions.insert().values(
                id=1,
                org_id=1,
                plan_id="plan-1",
                status="ACTIVE",
                billing_cycle="MONTHLY",
            )
        )
        db.commit()
    return TestClient(app)


def _make_legacy_client() -> TestClient:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)

    Partner.__table__.create(bind=engine)
    PartnerAccount.__table__.create(bind=engine)
    PartnerUserRole.__table__.create(bind=engine)
    PartnerLegalDetails.__table__.create(bind=engine)
    PartnerLegalProfile.__table__.create(bind=engine)
    PartnerPayoutRequest.__table__.create(bind=engine)
    SettlementPeriod.__table__.create(bind=engine)

    metadata = MetaData()
    orgs = Table(
        "orgs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(255), nullable=True),
        Column("status", String(32), nullable=True),
        Column("roles", JSON, nullable=True),
    )
    subscription_plans = Table(
        "subscription_plans",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("code", String(64), nullable=False),
        Column("version", Integer, nullable=True),
        Column("billing_period_months", Integer, nullable=True),
    )
    subscription_plan_modules = Table(
        "subscription_plan_modules",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("plan_id", String(64), nullable=False),
        Column("module_code", String(64), nullable=False),
        Column("enabled", Integer, nullable=False, default=1),
        Column("tier", String(32), nullable=True),
        Column("limits_json", JSON, nullable=True),
    )
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("plan_id", String(64), nullable=False),
        Column("status", String(32), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=True),
    )
    metadata.create_all(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(seed_partner_money.router, prefix="/api/core/v1/admin")
    app.state.testing_session_local = testing_session_local

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_user] = lambda: {"user_id": "admin-1", "role": "admin"}
    with testing_session_local() as db:
        db.execute(orgs.insert().values(id=1, name="demo-client", status="ACTIVE", roles=["CLIENT"]))
        db.execute(
            subscription_plans.insert().values(
                id="plan-1",
                code="CONTROL_INDIVIDUAL_1M",
                version=1,
                billing_period_months=1,
            )
        )
        db.execute(
            subscription_plan_modules.insert().values(
                plan_id="plan-1",
                module_code="ANALYTICS",
                enabled=1,
                tier="standard",
                limits_json={"exports_per_month": 10},
            )
        )
        db.execute(
            client_subscriptions.insert().values(
                id="legacy-sub-1",
                tenant_id=1,
                plan_id="plan-1",
                status="ACTIVE",
            )
        )
        db.commit()
    return TestClient(app)


def test_seed_partner_money_accepts_legacy_numeric_demo_org_id(monkeypatch: object) -> None:
    monkeypatch.setenv("NEFT_ENV", "dev")
    monkeypatch.setenv("NEFT_DEMO_ORG_ID", "1")
    client = _make_client()

    response = client.post(
        "/api/core/v1/admin/seed/partner-money",
        json={"email": "partner@neft.local", "org_name": "Demo Partner", "inn": "7700000000"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["partner_org_id"] == seed_partner_money.DEFAULT_DEMO_PARTNER_ORG_UUID
    assert payload["partner_email"] == "partner@neft.local"


def test_seed_partner_money_preserves_uuid_demo_org_id(monkeypatch: object) -> None:
    monkeypatch.setenv("NEFT_ENV", "dev")
    monkeypatch.setenv("NEFT_DEMO_ORG_ID", "11111111-1111-1111-1111-111111111111")
    client = _make_client()

    response = client.post(
        "/api/core/v1/admin/seed/partner-money",
        json={"email": "partner@neft.local", "org_name": "Demo Partner", "inn": "7700000000"},
    )

    assert response.status_code == 201
    assert response.json()["partner_org_id"] == "11111111-1111-1111-1111-111111111111"


def test_seed_partner_money_promotes_demo_finance_org_and_capabilities(monkeypatch: object) -> None:
    monkeypatch.setenv("NEFT_ENV", "dev")
    monkeypatch.setenv("NEFT_DEMO_ORG_ID", "1")
    monkeypatch.setenv("NEFT_DEMO_FINANCE_ORG_ID", "1")
    client = _make_client()

    response = client.post(
        "/api/core/v1/admin/seed/partner-money",
        json={"email": "partner@neft.local", "org_name": "Demo Partner", "inn": "7700000000"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["partner_org_id"] == seed_partner_money.DEFAULT_DEMO_PARTNER_ORG_UUID

    with client.app.state.testing_session_local() as session:
        orgs = Table("orgs", MetaData(), autoload_with=session.get_bind())
        overrides = Table("org_subscription_overrides", MetaData(), autoload_with=session.get_bind())
        snapshots = Table("org_entitlements_snapshot", MetaData(), autoload_with=session.get_bind())

        org = session.execute(select(orgs).where(orgs.c.id == 1)).mappings().one()
        assert sorted(org["roles"]) == ["CLIENT", "PARTNER"]

        override_keys = {
            row["feature_key"]
            for row in session.execute(select(overrides.c.feature_key)).mappings().all()
        }
        assert override_keys == {
            "feature.partner.core",
            "feature.partner.analytics",
            "feature.partner.catalog",
            "feature.partner.orders",
            "feature.partner.payouts",
            "feature.partner.pricing",
            "feature.partner.settlements",
        }

        snapshot = (
            session.execute(select(snapshots.c.entitlements_json).where(snapshots.c.org_id == 1))
            .mappings()
            .first()
        )
        assert snapshot is not None
        capabilities = set((snapshot["entitlements_json"] or {}).get("capabilities") or [])
        assert {
            "PARTNER_FINANCE_VIEW",
            "PARTNER_CATALOG",
            "PARTNER_PRICING",
            "PARTNER_ORDERS",
            "PARTNER_ANALYTICS",
            "PARTNER_PAYOUT_REQUEST",
            "PARTNER_SETTLEMENTS",
            "PARTNER_DOCUMENTS_LIST",
        }.issubset(capabilities)

        partner_profile = session.query(PartnerLegalProfile).filter(PartnerLegalProfile.partner_id == "1").one()
        assert partner_profile.legal_status.value == "VERIFIED"
        settlement_period = (
            session.query(SettlementPeriod)
            .filter(SettlementPeriod.partner_id == seed_partner_money.DEFAULT_DEMO_PARTNER_ORG_UUID)
            .one()
        )
        assert settlement_period.status.value == "APPROVED"


def test_seed_partner_money_recreates_missing_demo_finance_org(monkeypatch: object) -> None:
    monkeypatch.setenv("NEFT_ENV", "dev")
    monkeypatch.setenv("NEFT_DEMO_ORG_ID", "1")
    monkeypatch.setenv("NEFT_DEMO_FINANCE_ORG_ID", "1")
    client = _make_client()

    with client.app.state.testing_session_local() as session:
        orgs = Table("orgs", MetaData(), autoload_with=session.get_bind())
        session.execute(orgs.delete().where(orgs.c.id == 1))
        session.commit()

    response = client.post(
        "/api/core/v1/admin/seed/partner-money",
        json={"email": "partner@neft.local", "org_name": "Demo Partner", "inn": "7700000000"},
    )

    assert response.status_code == 201

    with client.app.state.testing_session_local() as session:
        orgs = Table("orgs", MetaData(), autoload_with=session.get_bind())
        org = session.execute(select(orgs).where(orgs.c.id == 1)).mappings().one()
        assert org["status"] == "ACTIVE"
        assert org["roles"] == ["PARTNER"]

        snapshot = get_org_entitlements_snapshot(session, org_id=1)
        capabilities = set((snapshot.entitlements or {}).get("capabilities") or [])
        assert {
            "PARTNER_CORE",
            "PARTNER_FINANCE_VIEW",
            "PARTNER_PAYOUT_REQUEST",
            "PARTNER_SETTLEMENTS",
        }.issubset(capabilities)

        detail_ids = {
            str(partner_id)
            for partner_id, in session.query(PartnerLegalDetails.partner_id).all()
        }
        assert seed_partner_money.DEFAULT_DEMO_PARTNER_ORG_UUID in detail_ids
        assert "1" in detail_ids


def test_seed_partner_money_enables_partner_finance_caps_on_legacy_entitlements(monkeypatch: object) -> None:
    monkeypatch.setenv("NEFT_ENV", "dev")
    monkeypatch.setenv("NEFT_DEMO_ORG_ID", "1")
    monkeypatch.setenv("NEFT_DEMO_FINANCE_ORG_ID", "1")
    client = _make_legacy_client()

    response = client.post(
        "/api/core/v1/admin/seed/partner-money",
        json={"email": "partner@neft.local", "org_name": "Demo Partner", "inn": "7700000000"},
    )

    assert response.status_code == 201

    with client.app.state.testing_session_local() as session:
        snapshot = get_org_entitlements_snapshot(session, org_id=1)
        capabilities = set((snapshot.entitlements or {}).get("capabilities") or [])
        features = (snapshot.entitlements or {}).get("features") or {}
        modules = (snapshot.entitlements or {}).get("modules") or {}

        assert {
            "PARTNER_CORE",
            "PARTNER_CATALOG",
            "PARTNER_PRICING",
            "PARTNER_ORDERS",
            "PARTNER_ANALYTICS",
            "PARTNER_FINANCE_VIEW",
            "PARTNER_PAYOUT_REQUEST",
            "PARTNER_SETTLEMENTS",
            "PARTNER_DOCUMENTS_LIST",
        }.issubset(capabilities)
        assert features["feature.partner.settlements"]["availability"] == "ENABLED"
        assert features["feature.partner.payouts"]["availability"] == "ENABLED"
        assert modules["PARTNER_SETTLEMENTS"]["enabled"] is True


def test_partner_role_keeps_finance_caps_when_entitlement_tables_are_absent() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session)
    metadata = MetaData()
    orgs = Table(
        "orgs",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(255), nullable=True),
        Column("status", String(32), nullable=True),
        Column("roles", JSON, nullable=True),
    )
    metadata.create_all(bind=engine)

    with testing_session_local() as session:
        session.execute(orgs.insert().values(id=1, name="demo-partner", status="ACTIVE", roles=["PARTNER"]))
        session.commit()

        snapshot = get_org_entitlements_snapshot(session, org_id=1)
        capabilities = set((snapshot.entitlements or {}).get("capabilities") or [])
        features = (snapshot.entitlements or {}).get("features") or {}
        modules = (snapshot.entitlements or {}).get("modules") or {}

    assert (snapshot.entitlements or {}).get("subscription") is None
    assert {
        "PARTNER_CORE",
        "PARTNER_CATALOG",
        "PARTNER_PRICING",
        "PARTNER_ORDERS",
        "PARTNER_ANALYTICS",
        "PARTNER_FINANCE_VIEW",
        "PARTNER_PAYOUT_REQUEST",
        "PARTNER_SETTLEMENTS",
        "PARTNER_DOCUMENTS_LIST",
    }.issubset(capabilities)
    assert "CLIENT_BILLING" not in capabilities
    assert "MARKETPLACE" not in capabilities
    assert features["feature.partner.settlements"]["availability"] == "ENABLED"
    assert features["feature.partner.payouts"]["availability"] == "ENABLED"
    assert modules["PARTNER_SETTLEMENTS"]["enabled"] is True


def test_seed_partner_money_normalizes_stale_demo_payout_requests(monkeypatch: object) -> None:
    monkeypatch.setenv("NEFT_ENV", "dev")
    monkeypatch.setenv("NEFT_DEMO_ORG_ID", "1")
    monkeypatch.setenv("NEFT_DEMO_FINANCE_ORG_ID", "1")
    client = _make_client()
    now = datetime.now(timezone.utc)

    with client.app.state.testing_session_local() as session:
        session.add(
            PartnerAccount(
                org_id="1",
                currency="RUB",
                balance_available=Decimal("5000"),
                balance_pending=Decimal("0"),
                balance_blocked=Decimal("1000"),
            )
        )
        session.add(
            PartnerPayoutRequest(
                partner_org_id="1",
                amount=Decimal("1000"),
                currency="RUB",
                status=PartnerPayoutRequestStatus.REQUESTED,
                created_at=now,
            )
        )
        session.commit()

    response = client.post(
        "/api/core/v1/admin/seed/partner-money",
        json={"email": "partner@neft.local", "org_name": "Demo Partner", "inn": "7700000000"},
    )

    assert response.status_code == 201

    with client.app.state.testing_session_local() as session:
        payout = session.query(PartnerPayoutRequest).filter(PartnerPayoutRequest.partner_org_id == "1").one()
        account = (
            session.query(PartnerAccount)
            .filter(PartnerAccount.org_id == "1", PartnerAccount.currency == "RUB")
            .one()
        )
        payout_created_at = payout.created_at
        if payout_created_at.tzinfo is None:
            payout_created_at = payout_created_at.replace(tzinfo=timezone.utc)

        assert payout.status == PartnerPayoutRequestStatus.REJECTED
        assert payout.processed_at is not None
        assert payout_created_at <= now - timedelta(days=7)
        assert Decimal(account.balance_blocked) == Decimal("0")
        assert Decimal(account.balance_available) == Decimal("6000")


def test_seed_partner_money_rebinds_partner_user_to_seeded_partner(monkeypatch: object) -> None:
    monkeypatch.setenv("NEFT_ENV", "dev")
    monkeypatch.setenv("NEFT_DEMO_ORG_ID", "1")
    monkeypatch.setattr(seed_partner_money, "_lookup_auth_user_id", lambda email, logger: "partner-user-1")
    client = _make_client()

    with client.app.state.testing_session_local() as session:
        legacy_partner_id = str(uuid4())
        session.add(
            Partner(
                id=legacy_partner_id,
                code="demo-partner",
                legal_name="Legacy Demo Partner",
                partner_type="OTHER",
                status="ACTIVE",
                contacts={"email": "partner@neft.local"},
            )
        )
        session.add(
            PartnerUserRole(
                partner_id=legacy_partner_id,
                user_id="partner-user-1",
                roles=["PARTNER_OWNER"],
            )
        )
        session.commit()

    response = client.post(
        "/api/core/v1/admin/seed/partner-money",
        json={"email": "partner@neft.local", "org_name": "Demo Partner", "inn": "7700000000"},
    )

    assert response.status_code == 201
    partner_org_id = response.json()["partner_org_id"]

    with client.app.state.testing_session_local() as session:
        bindings = session.query(PartnerUserRole).filter(PartnerUserRole.user_id == "partner-user-1").all()
        assert len(bindings) == 1
        assert str(bindings[0].partner_id) == partner_org_id
        assert bindings[0].roles == ["PARTNER_OWNER"]
