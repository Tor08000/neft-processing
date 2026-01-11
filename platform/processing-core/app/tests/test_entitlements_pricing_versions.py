from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.client import Client
from app.models.client_portal import ClientCard
from app.models.pricing import PriceSchedule, PriceScheduleStatus, PriceVersion, PriceVersionItem, PriceVersionStatus
from app.models.subscriptions_v1 import (
    ClientSubscription,
    SubscriptionModuleCode,
    SubscriptionPlan,
    SubscriptionPlanLimit,
    SubscriptionPlanModule,
    SubscriptionStatus,
)
from app.services import entitlements_service
from app.services.entitlements_service import assert_max_cards, assert_module_enabled
from app.services.pricing_versions import create_price_version, create_schedule, publish_price_version


@pytest.fixture(autouse=True)
def _prepare_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    entitlements_service._ENTITLEMENTS_CACHE.clear()
    yield
    entitlements_service._ENTITLEMENTS_CACHE.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def api_client():
    return TestClient(app)


def _create_plan(
    db,
    *,
    code: str,
    docs_enabled: bool = True,
    crm_enabled: bool = False,
) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        code=code,
        title=f"{code} Plan",
        description=None,
        is_active=True,
        billing_period_months=1,
        price_cents=0,
        discount_percent=0,
        bonus_multiplier_override=None,
        currency="RUB",
    )
    db.add(plan)
    db.flush()
    modules = {
        SubscriptionModuleCode.DOCS: docs_enabled,
        SubscriptionModuleCode.CRM: crm_enabled,
    }
    for module_code, enabled in modules.items():
        db.add(
            SubscriptionPlanModule(
                plan_id=plan.id,
                module_code=module_code,
                enabled=enabled,
                tier="basic",
                limits={},
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def _create_subscription(db, *, client_id: str, plan: SubscriptionPlan) -> ClientSubscription:
    subscription = ClientSubscription(
        tenant_id=1,
        client_id=client_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_at=datetime.now(timezone.utc),
        auto_renew=True,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def test_publish_new_price_version_affects_entitlements(session, api_client, admin_auth_headers):
    client_id = str(uuid4())
    plan = _create_plan(session, code="CONTROL")
    _create_subscription(session, client_id=client_id, plan=plan)

    now = datetime.now(timezone.utc)
    version_v1 = PriceVersion(
        id=str(uuid4()),
        name="V1 Pricing",
        status=PriceVersionStatus.PUBLISHED,
        created_at=now,
    )
    session.add(version_v1)
    session.flush()
    session.add(
        PriceVersionItem(
            price_version_id=version_v1.id,
            plan_code=plan.code,
            billing_period="MONTHLY",
            currency="RUB",
            base_price=Decimal("100.00"),
            setup_fee=None,
        )
    )
    session.add(
        PriceSchedule(
            id=str(uuid4()),
            price_version_id=version_v1.id,
            effective_from=now - timedelta(days=1),
            effective_to=now + timedelta(days=1),
            priority=0,
            status=PriceScheduleStatus.ACTIVE,
        )
    )
    subscription.current_price_version_id = version_v1.id
    session.commit()

    first_resp = api_client.get(
        "/api/v1/admin/entitlements/resolve",
        params={"client_id": client_id},
        headers=admin_auth_headers,
    )
    assert first_resp.status_code == 200
    first = first_resp.json()
    assert first["active_price_version_id"] == version_v1.id
    assert first["pricing"]["base_price"] == "100.00"

    version_v2 = create_price_version(session, name="V2 Pricing")
    session.add(
        PriceVersionItem(
            price_version_id=version_v2.id,
            plan_code=plan.code,
            billing_period="MONTHLY",
            currency="RUB",
            base_price=Decimal("120.00"),
            setup_fee=None,
        )
    )
    session.commit()
    publish_price_version(session, price_version_id=version_v2.id)
    create_schedule(
        session,
        price_version_id=version_v2.id,
        effective_from=now,
        effective_to=None,
        priority=10,
    )
    session.query(PriceSchedule).filter(PriceSchedule.price_version_id == version_v1.id).update(
        {"effective_to": now, "status": PriceScheduleStatus.EXPIRED}
    )
    session.commit()

    second_resp = api_client.get(
        "/api/v1/admin/entitlements/resolve",
        params={"client_id": client_id},
        headers=admin_auth_headers,
    )
    assert second_resp.status_code == 200
    second = second_resp.json()
    assert second["active_price_version_id"] == version_v2.id
    assert second["pricing"]["base_price"] == "120.00"


def test_module_gating_blocks_docs(session):
    client_id = str(uuid4())
    plan = _create_plan(session, code="FREE", docs_enabled=False)
    _create_subscription(session, client_id=client_id, plan=plan)

    with pytest.raises(HTTPException) as exc:
        assert_module_enabled(session, client_id=client_id, module_code="DOCS")
    assert exc.value.status_code == 403


def test_max_cards_limit_blocks_second_card(session):
    client_uuid = uuid4()
    client_id = str(client_uuid)
    plan = _create_plan(session, code="CONTROL")
    session.add(
        SubscriptionPlanLimit(
            plan_id=plan.id,
            limit_code="max_cards",
            value_int=1,
            value_decimal=None,
            value_text=None,
            value_json=None,
            period=None,
        )
    )
    session.add(Client(id=client_uuid, name="Client A"))
    _create_subscription(session, client_id=client_id, plan=plan)
    session.add(ClientCard(client_id=client_uuid, card_id="card-1", pan_masked="****1111", status="ACTIVE"))
    session.commit()

    with pytest.raises(HTTPException) as exc:
        assert_max_cards(session, client_id=client_id, delta=1)
    assert exc.value.status_code == 403


def test_crm_module_blocks_admin_subscription(session, api_client, admin_auth_headers):
    client_id = "client-crm-blocked"
    plan = _create_plan(session, code="BASIC", crm_enabled=False)
    _create_subscription(session, client_id=client_id, plan=plan)
    payload = {
        "tenant_id": 1,
        "tariff_plan_id": "BASIC",
        "status": "ACTIVE",
        "billing_cycle": "MONTHLY",
        "billing_day": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "paused_at": None,
        "ended_at": None,
        "meta": None,
    }
    resp = api_client.post(
        f"/api/v1/admin/crm/clients/{client_id}/subscriptions",
        json=payload,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403


def test_crm_module_allows_admin_subscription(session, api_client, admin_auth_headers):
    client_id = "client-crm-enabled"
    plan = _create_plan(session, code="PRO", crm_enabled=True)
    _create_subscription(session, client_id=client_id, plan=plan)
    payload = {
        "tenant_id": 1,
        "tariff_plan_id": "PRO",
        "status": "ACTIVE",
        "billing_cycle": "MONTHLY",
        "billing_day": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "paused_at": None,
        "ended_at": None,
        "meta": None,
    }
    resp = api_client.post(
        f"/api/v1/admin/crm/clients/{client_id}/subscriptions",
        json=payload,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
