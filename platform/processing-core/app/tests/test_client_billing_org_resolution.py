from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.routers import client_portal_v1
from app.models.subscriptions_v1 import (
    ClientSubscription,
    SubscriptionModuleCode,
    SubscriptionPlan,
    SubscriptionPlanModule,
    SubscriptionStatus,
)
from app.models.pricing import PriceVersion
from app.services import entitlements_v2_service
from app.services.billing_access import BillingActionKind, evaluate_entitlement


def test_client_billing_org_resolution_prefers_numeric_org_but_support_uses_uuid_client() -> None:
    client_id = str(uuid4())
    token = {
        "org_id": 101,
        "client_id": client_id,
        "tenant_id": 7,
    }

    assert client_portal_v1._resolve_org_id(token) == 101
    assert client_portal_v1._support_ticket_org_id(token) == client_id


def test_client_billing_org_resolution_falls_back_to_tenant_id() -> None:
    token = {"tenant_id": 33, "client_id": str(uuid4())}

    assert client_portal_v1._resolve_org_id(token) == 33


def test_client_billing_org_resolution_rejects_non_numeric_claims() -> None:
    token = {"org_id": str(uuid4()), "client_id": str(uuid4())}

    try:
        client_portal_v1._resolve_org_id(token)
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "invalid_org"
    else:  # pragma: no cover - defensive
        raise AssertionError("expected invalid_org")


def test_billing_access_resolves_uuid_client_token_from_subscription(monkeypatch) -> None:
    monkeypatch.setattr(entitlements_v2_service, "DB_SCHEMA", None, raising=False)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    for table in (PriceVersion.__table__, SubscriptionPlan.__table__, SubscriptionPlanModule.__table__, ClientSubscription.__table__):
        table.create(bind=engine)

    client_id = str(uuid4())
    plan_id = f"plan-{uuid4()}"
    token = {"client_id": client_id, "tenant_id": str(uuid4()), "roles": ["CLIENT_OWNER"]}
    with SessionLocal() as db:
        db.add(SubscriptionPlan(id=plan_id, code="CLIENT_CORE", title="Client Core", is_active=True))
        db.add(
            SubscriptionPlanModule(
                plan_id=plan_id,
                module_code=SubscriptionModuleCode.FUEL_CORE,
                enabled=True,
                tier="control",
                limits={},
            )
        )
        db.add(
            ClientSubscription(
                id=str(uuid4()),
                tenant_id=77,
                client_id=client_id,
                plan_id=plan_id,
                status=SubscriptionStatus.ACTIVE,
                start_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        decision = evaluate_entitlement(
            db,
            token=token,
            feature_keys=["feature.portal.entities"],
            action_kind=BillingActionKind.WRITE,
        )

    assert decision.allowed is True


def test_client_plan_surface_excludes_partner_plans_and_serializes_module_values() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    for table in (SubscriptionPlan.__table__, SubscriptionPlanModule.__table__):
        table.create(bind=engine)

    with SessionLocal() as db:
        client_plan = SubscriptionPlan(id="client-plan", code="CONTROL_INDIVIDUAL_1M", title="Client", is_active=True)
        partner_plan = SubscriptionPlan(id="partner-plan", code="PARTNER_SERVICE_PRO_1M", title="Partner", is_active=True)
        db.add_all([client_plan, partner_plan])
        db.add_all(
            [
                SubscriptionPlanModule(
                    plan_id="client-plan",
                    module_code=SubscriptionModuleCode.FUEL_CORE,
                    enabled=True,
                    tier="control",
                    limits={},
                ),
                SubscriptionPlanModule(
                    plan_id="partner-plan",
                    module_code=SubscriptionModuleCode.FUEL_CORE,
                    enabled=False,
                    tier="off",
                    limits={},
                ),
            ]
        )
        db.commit()

        modules, _limits = client_portal_v1._plan_modules_map(db, plan_id="client-plan")

        assert "FUEL_CORE" in modules
        assert client_portal_v1._is_client_visible_subscription_plan(db, client_plan) is True
        assert client_portal_v1._is_client_visible_subscription_plan(db, partner_plan) is False
