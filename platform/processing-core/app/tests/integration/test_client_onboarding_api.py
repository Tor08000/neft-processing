from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.main as app_main
from app.db import Base, engine, get_sessionmaker
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.models.feature_flags import FeatureFlag
from app.models.fuel import FleetOfflineProfile
from app.models.pricing import PriceVersion
from app.models.subscriptions_v1 import ClientSubscription, SubscriptionModuleCode, SubscriptionPlan, SubscriptionPlanModule
from app.routers import client_onboarding, client_portal_v1
from app.services import client_auth, client_fetch, portal_me

TEST_TABLES = [
    FleetOfflineProfile.__table__,
    PriceVersion.__table__,
    Client.__table__,
    AuditLog.__table__,
    FeatureFlag.__table__,
    ClientOnboardingContract.__table__,
    ClientOnboarding.__table__,
    SubscriptionPlan.__table__,
    SubscriptionPlanModule.__table__,
    ClientSubscription.__table__,
]


@pytest.fixture(autouse=True)
def clean_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
    monkeypatch.setattr(client_auth, "EXPECTED_ISSUER", "neft-auth", raising=False)
    monkeypatch.setattr(client_auth, "EXPECTED_AUDIENCE", "neft-client", raising=False)
    monkeypatch.setattr(client_onboarding, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(client_portal_v1, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(client_fetch, "DB_SCHEMA", None, raising=False)
    monkeypatch.setattr(portal_me, "DB_SCHEMA", None, raising=False)
    Base.metadata.drop_all(bind=engine, tables=TEST_TABLES)
    Base.metadata.create_all(bind=engine, tables=TEST_TABLES)
    yield
    Base.metadata.drop_all(bind=engine, tables=TEST_TABLES)


@pytest.mark.integration
def test_client_onboarding_legacy_flow(make_jwt):
    session = get_sessionmaker()()
    try:
        session.add(FeatureFlag(key="self_signup_enabled", on=True))
        session.add(FeatureFlag(key="auto_activate_after_sign", on=True))
        session.commit()
    finally:
        session.close()

    token = make_jwt(
        roles=("CLIENT_OWNER",),
        sub="user-123",
        extra={"aud": "neft-client", "portal": "client", "subject_type": "client_user"},
    )
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        status = api_client.get("/api/core/client/onboarding/status")
        assert status.status_code == 200
        assert status.json() == {"step": "PROFILE", "status": "DRAFT", "client_type": None}

        profile_payload = {
            "name": "ACME LLC",
            "inn": "7700000000",
            "kpp": "770001001",
            "ogrn": "1234567890123",
            "address": "Moscow, Red Square",
            "contacts": {"email": "ops@acme.test"},
            "client_type": "LEGAL",
        }
        profile = api_client.post("/api/core/client/onboarding/profile-legacy", json=profile_payload)
        assert profile.status_code == 200
        assert profile.json() == {"step": "CONTRACT", "status": "DRAFT"}

        generate = api_client.post("/api/core/client/onboarding/contract/generate")
        assert generate.status_code == 200
        contract_payload = generate.json()
        assert contract_payload["contract_id"]
        assert contract_payload["pdf_url"]
        assert contract_payload["version"] == 1

        contract = api_client.get("/api/core/client/onboarding/contract")
        assert contract.status_code == 200
        assert contract.json()["status"] == "DRAFT"

        sign = api_client.post("/api/core/client/onboarding/contract/sign")
        assert sign.status_code == 200
        assert sign.json()["status"] == "ACTIVE"

    session = get_sessionmaker()()
    try:
        onboarding = (
            session.query(ClientOnboarding)
            .filter(ClientOnboarding.owner_user_id == "user-123")
            .one()
        )
        contract = (
            session.query(ClientOnboardingContract)
            .filter(ClientOnboardingContract.id == contract_payload["contract_id"])
            .one()
        )
        client = session.query(Client).filter(Client.id == UUID(str(onboarding.client_id))).one()
        assert onboarding.status == "ACTIVE"
        assert onboarding.step == "ACTIVATION"
        assert contract.status == "SIGNED_SIMPLE"
        assert client.status == "ACTIVE"
    finally:
        session.close()


@pytest.mark.integration
def test_client_onboarding_legacy_profile_idempotent(make_jwt):
    session = get_sessionmaker()()
    try:
        session.add(FeatureFlag(key="self_signup_enabled", on=True))
        session.commit()
    finally:
        session.close()

    token = make_jwt(
        roles=("CLIENT_OWNER",),
        sub="user-456",
        extra={"aud": "neft-client", "portal": "client", "subject_type": "client_user"},
    )
    profile_payload = {
        "name": "ООО ТЕСТ",
        "inn": "7707083893",
        "kpp": "770701001",
        "ogrn": "1027700132195",
        "address": "Москва",
        "org_type": "LEGAL",
    }
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        first = api_client.post("/api/core/client/onboarding/profile-legacy", json=profile_payload)
        assert first.status_code == 200
        assert first.json() == {"step": "CONTRACT", "status": "DRAFT"}

        second = api_client.post("/api/core/client/onboarding/profile-legacy", json=profile_payload)
        assert second.status_code == 200
        assert second.json() == {"step": "CONTRACT", "status": "DRAFT"}

        missing = api_client.post("/api/core/client/onboarding/profile-legacy", json={})
        assert missing.status_code == 422

    session = get_sessionmaker()()
    try:
        onboardings = (
            session.query(ClientOnboarding)
            .filter(ClientOnboarding.owner_user_id == "user-456")
            .all()
        )
        assert len(onboardings) == 1
        client_id = onboardings[0].client_id
        client = session.query(Client).filter(Client.id == UUID(str(client_id))).one()
        assert client.name == "ООО ТЕСТ"
    finally:
        session.close()


@pytest.mark.integration
def test_client_onboarding_activate_requires_canonical_prerequisites(make_jwt):
    session = get_sessionmaker()()
    try:
        plan = SubscriptionPlan(
            id="plan-pro",
            code="PRO",
            title="Pro",
            is_active=True,
            billing_period_months=1,
            price_cents=1000,
            discount_percent=0,
            currency="RUB",
        )
        session.add(plan)
        session.add(
            SubscriptionPlanModule(
                plan_id=plan.id,
                module_code=SubscriptionModuleCode.DOCS,
                enabled=True,
                tier="pro",
                limits={},
            )
        )
        session.commit()
    finally:
        session.close()

    user_id = "22222222-2222-2222-2222-222222222222"
    token = make_jwt(
        roles=("CLIENT_OWNER",),
        sub=user_id,
        extra={
            "aud": "neft-client",
            "portal": "client",
            "subject_type": "client_user",
            "user_id": user_id,
            "tenant_id": 1,
            "entitlements_snapshot": {
                "org_roles": ["CLIENT"],
                "capabilities": ["client_portal_access"],
                "modules": {"DOCS": {"enabled": True}},
                "features": {},
                "limits": {},
            },
        },
    )

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        profile = api_client.post(
            "/api/core/client/onboarding/profile",
            json={
                "org_type": "LEGAL",
                "name": "BETA LLC",
                "inn": "7702234567",
                "kpp": "770201001",
                "ogrn": "2234567890123",
                "address": "Moscow, Tverskaya 1",
            },
        )
        assert profile.status_code == 200
        profile_payload = profile.json()

        client_context_token = make_jwt(
            roles=("CLIENT_OWNER",),
            sub=user_id,
            client_id=profile_payload["id"],
            extra={
                "aud": "neft-client",
                "portal": "client",
                "subject_type": "client_user",
                "user_id": user_id,
                "tenant_id": 1,
                "entitlements_snapshot": {
                    "org_roles": ["CLIENT"],
                    "capabilities": ["client_portal_access"],
                    "modules": {"DOCS": {"enabled": True}},
                    "features": {},
                    "limits": {},
                },
            },
        )
        client_context_headers = {"Authorization": f"Bearer {client_context_token}"}

        missing_subscription = api_client.post(
            "/api/core/client/onboarding/activate",
            headers=client_context_headers,
        )
        assert missing_subscription.status_code == 409
        assert missing_subscription.json()["error"]["message"] == "subscription_missing"

        session = get_sessionmaker()()
        try:
            onboarding = session.query(ClientOnboarding).filter(ClientOnboarding.client_id == profile_payload["id"]).one()
            client = session.get(Client, UUID(profile_payload["id"]))
            assert onboarding.step == "PLAN"
            assert onboarding.status != "ACTIVE"
            assert client is not None
            assert client.status != "ACTIVE"
        finally:
            session.close()

        subscription = api_client.post(
            "/api/core/client/subscription/select",
            json={"plan_code": "PRO", "auto_renew": False},
            headers=client_context_headers,
        )
        assert subscription.status_code == 200, subscription.text

        missing_contract = api_client.post(
            "/api/core/client/onboarding/activate",
            headers=client_context_headers,
        )
        assert missing_contract.status_code == 409
        assert missing_contract.json()["error"]["message"] == "contract_not_found"

        generate = api_client.post("/api/core/client/contracts/generate", headers=client_context_headers)
        assert generate.status_code == 200
        contract_payload = generate.json()
        assert contract_payload["status"] == "DRAFT"

        unsigned_contract = api_client.post(
            "/api/core/client/onboarding/activate",
            headers=client_context_headers,
        )
        assert unsigned_contract.status_code == 409
        assert unsigned_contract.json()["error"]["message"] == "contract_not_signed"

        session = get_sessionmaker()()
        try:
            onboarding = session.query(ClientOnboarding).filter(ClientOnboarding.client_id == profile_payload["id"]).one()
            contract = (
                session.query(ClientOnboardingContract)
                .filter(ClientOnboardingContract.id == contract_payload["contract_id"])
                .one()
            )
            client = session.get(Client, UUID(profile_payload["id"]))
            assert onboarding.step == "CONTRACT"
            assert onboarding.status != "ACTIVE"
            assert contract.status == "DRAFT"
            assert client is not None
            assert client.status != "ACTIVE"
        finally:
            session.close()

        sign = api_client.post(
            "/api/core/client/contracts/sign-simple",
            json={"otp": "123456"},
            headers=client_context_headers,
        )
        assert sign.status_code == 200
        assert sign.json()["status"] == "SIGNED_SIMPLE"

        activate = api_client.post(
            "/api/core/client/onboarding/activate",
            headers=client_context_headers,
        )
        assert activate.status_code == 200
        assert activate.json()["status"] == "ACTIVE"

@pytest.mark.integration
def test_client_onboarding_current_flow_handoff_to_portal_me(make_jwt):
    session = get_sessionmaker()()
    try:
        plan = SubscriptionPlan(
            id="plan-pro",
            code="PRO",
            title="Pro",
            is_active=True,
            billing_period_months=1,
            price_cents=1000,
            discount_percent=0,
            currency="RUB",
        )
        session.add(plan)
        session.add(
            SubscriptionPlanModule(
                plan_id=plan.id,
                module_code=SubscriptionModuleCode.DOCS,
                enabled=True,
                tier="pro",
                limits={},
            )
        )
        session.commit()
    finally:
        session.close()

    user_id = "11111111-1111-1111-1111-111111111111"
    token = make_jwt(
        roles=("CLIENT_OWNER",),
        sub=user_id,
        extra={
            "aud": "neft-client",
            "portal": "client",
            "subject_type": "client_user",
            "user_id": user_id,
            "tenant_id": 1,
            "entitlements_snapshot": {
                "org_roles": ["CLIENT"],
                "capabilities": ["client_portal_access"],
                "modules": {"DOCS": {"enabled": True}},
                "features": {},
                "limits": {},
            },
        },
    )

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api_client:
        profile = api_client.post(
            "/api/core/client/onboarding/profile",
            json={
                "org_type": "LEGAL",
                "name": "ACME LLC",
                "inn": "7701234567",
                "kpp": "770101001",
                "ogrn": "1234567890123",
                "address": "Moscow, Red Square",
            },
        )
        assert profile.status_code == 200
        profile_payload = profile.json()
        assert profile_payload["name"] == "ACME LLC"
        assert profile_payload["status"] == "ONBOARDING"

        session = get_sessionmaker()()
        try:
            client_rows = session.execute(text("select id, name, status from clients")).all()
            assert client_rows, client_rows
            assert session.get(Client, UUID(profile_payload["id"])) is not None, client_rows
        finally:
            session.close()

        client_context_token = make_jwt(
            roles=("CLIENT_OWNER",),
            sub=user_id,
            client_id=profile_payload["id"],
            extra={
                "aud": "neft-client",
                "portal": "client",
                "subject_type": "client_user",
                "user_id": user_id,
                "tenant_id": 1,
                "entitlements_snapshot": {
                    "org_roles": ["CLIENT"],
                    "capabilities": ["client_portal_access"],
                    "modules": {"DOCS": {"enabled": True}},
                    "features": {},
                    "limits": {},
                },
            },
        )
        client_context_headers = {"Authorization": f"Bearer {client_context_token}"}

        subscription = api_client.post(
            "/api/core/client/subscription/select",
            json={"plan_code": "PRO", "auto_renew": False},
            headers=client_context_headers,
        )
        assert subscription.status_code == 200, subscription.text
        assert subscription.json()["plan_code"] == "PRO"

        generate = api_client.post("/api/core/client/contracts/generate", headers=client_context_headers)
        assert generate.status_code == 200
        contract_payload = generate.json()
        assert contract_payload["contract_id"]
        assert contract_payload["status"] == "DRAFT"

        sign = api_client.post(
            "/api/core/client/contracts/sign-simple",
            json={"otp": "123456"},
            headers=client_context_headers,
        )
        assert sign.status_code == 200
        assert sign.json()["status"] == "SIGNED_SIMPLE"

        portal = api_client.get("/api/core/portal/me", headers=client_context_headers)

    assert portal.status_code == 200
    payload = portal.json()
    assert payload["org"] is not None
    assert payload["org"]["name"] == "ACME LLC"
    assert payload["org"]["inn"] == "7701234567"
    assert payload["org_status"] == "ACTIVE"
    assert payload["subscription"] is not None
    assert payload["subscription"]["plan_code"] == "PRO"
    assert payload["access_state"] == "ACTIVE"
    assert payload["access_reason"] is None
