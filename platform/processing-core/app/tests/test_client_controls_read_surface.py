from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models.client import Client
from app.models.client_limits import ClientLimit
from app.models.client_user_roles import ClientUserRole
from app.models.client_users import ClientUser
from app.models.crm import CRMClient, CRMClientStatus, CRMFeatureFlag, CRMFeatureFlagType
from app.models.fuel import FleetOfflineProfile
from app.models.pricing import PriceVersion
from app.models.subscriptions_v1 import (
    ClientSubscription,
    SubscriptionPlan,
    SubscriptionPlanModule,
    SubscriptionModuleCode,
    SubscriptionStatus,
)


def _client_headers(make_jwt, *, client_id: str, tenant_id: int, roles: tuple[str, ...]) -> dict[str, str]:
    token = make_jwt(
        roles=roles,
        client_id=client_id,
        extra={"tenant_id": tenant_id, "aud": "neft-client"},
    )
    return {"Authorization": f"Bearer {token}"}


def _build_session_factory() -> tuple[sessionmaker[Session], Table, object]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    users_table = Table(
        "users",
        MetaData(),
        Column("id", String(64), primary_key=True),
        Column("email", String),
        Column("full_name", String),
    )

    Base.metadata.create_all(
        bind=engine,
        tables=[
            FleetOfflineProfile.__table__,
            Client.__table__,
            ClientLimit.__table__,
            ClientUser.__table__,
            ClientUserRole.__table__,
            PriceVersion.__table__,
            SubscriptionPlan.__table__,
            SubscriptionPlanModule.__table__,
            ClientSubscription.__table__,
            CRMClient.__table__,
            CRMFeatureFlag.__table__,
        ],
    )
    users_table.create(bind=engine)

    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return testing_session_local, users_table, engine


@pytest.fixture(autouse=True)
def _allow_mock_providers_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")


def test_client_controls_read_surface_returns_limits_services_and_features(make_jwt) -> None:
    SessionLocal, users_table, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    tenant_id = 42
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls Demo", status="ACTIVE"))
            db.add_all(
                [
                    ClientLimit(
                        id=1,
                        client_id=client_uuid,
                        limit_type="DAILY_AMOUNT",
                        amount=5000,
                        currency="RUB",
                        used_amount=4500,
                        period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
                        period_end=datetime(2026, 3, 31, tzinfo=timezone.utc),
                    ),
                    ClientLimit(
                        id=2,
                        client_id=client_uuid,
                        limit_type="MONTHLY_COUNT",
                        amount=100,
                        currency="RUB",
                        used_amount=25,
                        period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
                        period_end=datetime(2026, 3, 31, tzinfo=timezone.utc),
                    ),
                ]
            )
            db.add(SubscriptionPlan(id="plan-controls", code="FREE_BASE", title="Free Base", is_active=True, billing_period_months=0, price_cents=0, discount_percent=0, currency="RUB"))
            db.add_all(
                [
                    SubscriptionPlanModule(plan_id="plan-controls", module_code=SubscriptionModuleCode.MARKETPLACE, enabled=True, tier="free", limits={"marketplace_discount_percent": 0}),
                    SubscriptionPlanModule(plan_id="plan-controls", module_code=SubscriptionModuleCode.DOCS, enabled=False, tier="basic", limits={}),
                ]
            )
            db.add(
                ClientSubscription(
                    id="sub-controls",
                    tenant_id=tenant_id,
                    client_id=client_id,
                    plan_id="plan-controls",
                    status=SubscriptionStatus.ACTIVE,
                    start_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                    auto_renew=False,
                    current_price_version_id=None,
                )
            )
            db.add(
                CRMClient(
                    id=client_id,
                    tenant_id=tenant_id,
                    legal_name="Client Controls Demo LLC",
                    country="RU",
                    timezone="Europe/Moscow",
                    status=CRMClientStatus.ACTIVE,
                )
            )
            db.add_all(
                [
                    CRMFeatureFlag(
                        tenant_id=tenant_id,
                        client_id=client_id,
                        feature=CRMFeatureFlagType.FUEL_ENABLED,
                        enabled=True,
                    ),
                    CRMFeatureFlag(
                        tenant_id=tenant_id,
                        client_id=client_id,
                        feature=CRMFeatureFlagType.DOCUMENTS_ENABLED,
                        enabled=False,
                    ),
                ]
            )
            db.commit()

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=tenant_id, roles=("CLIENT_USER",))
        with TestClient(app, headers=headers) as api_client:
            limits_response = api_client.get("/api/core/client/limits")
            services_response = api_client.get("/api/core/client/services")
            features_response = api_client.get("/api/core/client/features")

        assert limits_response.status_code == 200
        limits_body = limits_response.json()
        assert limits_body["status"] == "NEAR_LIMIT"
        assert len(limits_body["amount_limits"]) == 1
        assert len(limits_body["operation_limits"]) == 1
        assert limits_body["service_limits"] == []
        assert limits_body["partner_limits"] == []
        assert limits_body["station_limits"] == []
        assert limits_body["amount_limits"][0]["type"] == "DAILY_AMOUNT"
        assert limits_body["amount_limits"][0]["status"] == "NEAR_LIMIT"
        assert limits_body["operation_limits"][0]["type"] == "MONTHLY_COUNT"
        assert limits_body["operation_limits"][0]["status"] == "OK"

        assert services_response.status_code == 200
        services_body = services_response.json()
        assert [item["id"] for item in services_body["items"]] == ["DOCS", "MARKETPLACE"]
        assert services_body["items"][0]["status"] == "DISABLED"
        assert services_body["items"][1]["status"] == "ENABLED"

        assert features_response.status_code == 200
        features_body = features_response.json()
        assert features_body["items"] == [
            {
                "key": "DOCUMENTS_ENABLED",
                "description": "?????? ? ??????????",
                "status": "OFF",
                "scope": "client",
            },
            {
                "key": "FUEL_ENABLED",
                "description": "?????? ? ????????? ?????????",
                "status": "ON",
                "scope": "client",
            },
        ]
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_client_limits_route_returns_grouped_shape_when_empty(make_jwt) -> None:
    SessionLocal, _users_table, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls Empty", status="ACTIVE"))
            db.commit()

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=1, roles=("CLIENT_USER",))
        with TestClient(app, headers=headers) as api_client:
            response = api_client.get("/api/core/client/limits")

        assert response.status_code == 200
        body = response.json()
        assert body["amount_limits"] == []
        assert body["operation_limits"] == []
        assert body["service_limits"] == []
        assert body["partner_limits"] == []
        assert body["station_limits"] == []
        assert body["items"] == []
        assert body["status"] is None
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_client_users_route_regression_shape_for_admin(make_jwt) -> None:
    SessionLocal, users_table, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls Users", status="ACTIVE"))
            db.add(ClientUser(client_id=client_id, user_id="user-1", status="ACTIVE"))
            db.add(ClientUserRole(client_id=client_id, user_id="user-1", roles=["CLIENT_OWNER"]))
            db.execute(users_table.insert().values(id="user-1", email="owner@demo.test", full_name="Owner Demo"))
            db.commit()

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=1, roles=("CLIENT_ADMIN",))
        with TestClient(app, headers=headers) as api_client:
            response = api_client.get("/api/core/client/users")

        assert response.status_code == 200
        assert response.json() == {
            "items": [
                {
                    "user_id": "user-1",
                    "email": "owner@demo.test",
                    "full_name": "Owner Demo",
                    "status": "ACTIVE",
                    "roles": ["CLIENT_OWNER"],
                }
            ]
        }
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_client_users_route_is_forbidden_for_non_admin(make_jwt) -> None:
    SessionLocal, _users_table, engine = _build_session_factory()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client_uuid = uuid4()
    client_id = str(client_uuid)
    try:
        with SessionLocal() as db:
            db.add(Client(id=client_uuid, name="Client Controls Users", status="ACTIVE"))
            db.commit()

        headers = _client_headers(make_jwt, client_id=client_id, tenant_id=1, roles=("CLIENT_USER",))
        with TestClient(app, headers=headers) as api_client:
            response = api_client.get("/api/core/client/users")

        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
