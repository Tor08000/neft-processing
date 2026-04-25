from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.redis import get_redis
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.subscriptions_v1 import (
    ClientSubscription,
    SubscriptionModuleCode,
    SubscriptionPlan,
    SubscriptionPlanLimit,
    SubscriptionPlanModule,
    SubscriptionStatus,
)
from app.routers.client.marketplace_recommendations import router as marketplace_recommendations_router
from app.routers.portal import client_router as portal_client_router
from app.security.client_auth import require_client_user
from app.security.rbac.principal import Principal, get_principal
from app.services import entitlements_service


CURRENT_TOKEN: dict | None = None
CURRENT_PRINCIPAL: Principal | None = None


@pytest.fixture(autouse=True)
def _prepare_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    entitlements_service._ENTITLEMENTS_CACHE.clear()
    monkeypatch.setattr(entitlements_service, "DB_SCHEMA", None, raising=False)
    yield
    entitlements_service._ENTITLEMENTS_CACHE.clear()


def _build_client_principal(client_id: str) -> Principal:
    return Principal(
        user_id=None,
        roles={"client_user"},
        scopes=set(),
        client_id=UUID(client_id),
        partner_id=None,
        is_admin=False,
        raw_claims={"client_id": client_id, "roles": ["client_user"]},
    )


def _build_session_factory() -> tuple[sessionmaker[Session], object]:
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
    for table in (
        SubscriptionPlan.__table__,
        SubscriptionPlanModule.__table__,
        SubscriptionPlanLimit.__table__,
        ClientSubscription.__table__,
    ):
        table.create(bind=engine)
    return SessionLocal, engine


def _seed_marketplace_subscription(db: Session, *, client_id: str, enabled: bool) -> None:
    plan_id = f"plan-{uuid4()}"
    db.add(SubscriptionPlan(id=plan_id, code=f"PLAN_{uuid4().hex[:8].upper()}", title="Marketplace", is_active=True))
    db.add(
        SubscriptionPlanModule(
            plan_id=plan_id,
            module_code=SubscriptionModuleCode.MARKETPLACE,
            enabled=enabled,
            tier="base",
            limits={},
        )
    )
    db.add(
        ClientSubscription(
            id=str(uuid4()),
            tenant_id=1,
            client_id=client_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
            start_at=datetime.now(timezone.utc),
            auto_renew=False,
        )
    )
    db.commit()


def test_client_marketplace_recommendations_require_marketplace_module() -> None:
    global CURRENT_TOKEN
    SessionLocal, engine = _build_session_factory()
    CURRENT_TOKEN = {"client_id": str(uuid4()), "tenant_id": str(uuid4()), "user_id": str(uuid4())}
    with SessionLocal() as db:
        _seed_marketplace_subscription(db, client_id=str(CURRENT_TOKEN["client_id"]), enabled=False)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(marketplace_recommendations_router, prefix="/api/v1")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_require_client_user() -> dict:
        if CURRENT_TOKEN is None:
            raise RuntimeError("token_not_set")
        return CURRENT_TOKEN

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: None
    app.dependency_overrides[require_client_user] = override_require_client_user

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/marketplace/client/recommendations")
        assert response.status_code == 403
        assert response.json() == {"detail": "feature_not_included"}
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        CURRENT_TOKEN = None


def test_client_portal_marketplace_sla_requires_marketplace_module() -> None:
    global CURRENT_PRINCIPAL
    SessionLocal, engine = _build_session_factory()
    client_id = str(uuid4())
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    with SessionLocal() as db:
        _seed_marketplace_subscription(db, client_id=client_id, enabled=False)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(portal_client_router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_principal() -> Principal:
        if CURRENT_PRINCIPAL is None:
            raise RuntimeError("principal_not_set")
        return CURRENT_PRINCIPAL

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_principal] = override_get_principal

    try:
        with TestClient(app) as client:
            response = client.get("/api/client/marketplace/orders/order-1/sla")
        assert response.status_code == 403
        assert response.json() == {"detail": "feature_not_included"}
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        CURRENT_PRINCIPAL = None
