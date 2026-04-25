from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.db import Base, get_db
from app.models.audit_log import AuditLog
from app.models.marketplace_catalog import MarketplaceProductCard, MarketplaceService
from app.models.marketplace_moderation import MarketplaceModerationAudit, MarketplaceModerationEntityType
from app.models.marketplace_offers import MarketplaceOffer
from app.routers.admin.marketplace_moderation import router as moderation_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context

MARKETPLACE_MODERATION_TEST_TABLES = (
    AuditLog.__table__,
    MarketplaceModerationAudit.__table__,
    MarketplaceOffer.__table__,
    MarketplaceProductCard.__table__,
    MarketplaceService.__table__,
)


@pytest.fixture()
def db_session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    SessionLocal = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine, tables=list(MARKETPLACE_MODERATION_TEST_TABLES))
    try:
        yield SessionLocal
    finally:
        Base.metadata.drop_all(bind=engine, tables=list(MARKETPLACE_MODERATION_TEST_TABLES))
        engine.dispose()


@pytest.fixture()
def db_session(db_session_factory) -> Session:
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client(db_session_factory) -> TestClient:
    app = FastAPI()
    app.include_router(moderation_router, prefix="/api/core/v1/admin")

    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_user] = lambda: {"user_id": str(uuid4()), "roles": ["admin"]}

    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _cleanup_tables(db_session: Session):
    db_session.query(AuditLog).delete()
    db_session.query(MarketplaceModerationAudit).delete()
    db_session.query(MarketplaceOffer).delete()
    db_session.query(MarketplaceProductCard).delete()
    db_session.query(MarketplaceService).delete()
    db_session.commit()


@pytest.fixture(autouse=True)
def _stub_product_media(monkeypatch):
    monkeypatch.setattr(
        "app.services.marketplace_catalog_service.MarketplaceCatalogService.list_product_media",
        lambda self, product_id: [],
    )


def _seed_subjects(db: Session, partner_id: str) -> tuple[str, str]:
    product = MarketplaceProductCard(
        id=str(uuid4()),
        partner_id=partner_id,
        title="Product",
        description="Desc",
        category="Category",
        status="PENDING_REVIEW",
        tags=[],
        attributes={},
        variants=[],
    )
    service = MarketplaceService(
        id=str(uuid4()),
        partner_id=partner_id,
        title="Service",
        description="Desc",
        category="Category",
        status="PENDING_REVIEW",
        tags=[],
        attributes={},
        duration_min=30,
        requirements=None,
    )
    db.add(product)
    db.add(service)
    db.commit()
    return str(product.id), str(service.id)


def _seed_offer(db: Session, partner_id: str, subject_id: str) -> MarketplaceOffer:
    offer = MarketplaceOffer(
        id=str(uuid4()),
        partner_id=partner_id,
        subject_type="PRODUCT",
        subject_id=subject_id,
        title_override="Offer",
        description_override="Desc",
        status="PENDING_REVIEW",
        moderation_comment=None,
        currency="RUB",
        price_model="FIXED",
        price_amount=100,
        price_min=None,
        price_max=None,
        vat_rate=None,
        terms={},
        geo_scope="ALL_PARTNER_LOCATIONS",
        location_ids=[],
        region_code=None,
        entitlement_scope="ALL_CLIENTS",
        allowed_subscription_codes=[],
        allowed_client_ids=[],
        valid_from=None,
        valid_to=None,
    )
    db.add(offer)
    db.commit()
    return offer


def test_queue_returns_pending_items(api_client: TestClient, db_session: Session) -> None:
    partner_id = str(uuid4())
    product_id, _ = _seed_subjects(db_session, partner_id)
    _seed_offer(db_session, partner_id, product_id)

    response = api_client.get("/api/core/v1/admin/marketplace/moderation/queue", params={"status": "PENDING_REVIEW"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    types = {item["type"] for item in payload["items"]}
    assert types == {"PRODUCT", "SERVICE", "OFFER"}


def test_approve_transitions_product_card(api_client: TestClient, db_session: Session) -> None:
    partner_id = str(uuid4())
    product_id, _ = _seed_subjects(db_session, partner_id)

    response = api_client.post(f"/api/core/v1/admin/marketplace/products/{product_id}:approve")
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"

    card = db_session.query(MarketplaceProductCard).filter(MarketplaceProductCard.id == product_id).one()
    assert card.status == "ACTIVE"


def test_reject_offer_creates_audit(api_client: TestClient, db_session: Session) -> None:
    partner_id = str(uuid4())
    product_id, _ = _seed_subjects(db_session, partner_id)
    offer = _seed_offer(db_session, partner_id, product_id)

    response = api_client.post(
        f"/api/core/v1/admin/marketplace/offers/{offer.id}:reject",
        json={"reason_code": "MISSING_INFO", "comment": "Missing details"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DRAFT"

    audit = (
        db_session.query(MarketplaceModerationAudit)
        .filter(
            MarketplaceModerationAudit.entity_type == MarketplaceModerationEntityType.OFFER,
            MarketplaceModerationAudit.entity_id == str(offer.id),
        )
        .one()
    )
    assert audit.action.value == "REJECT"
    assert audit.reason_code == "MISSING_INFO"
    assert audit.comment == "Missing details"


def test_marketplace_approve_denies_finance_only_admin(
    api_client: TestClient,
    db_session_factory,
    db_session: Session,
) -> None:
    partner_id = str(uuid4())
    product_id, _ = _seed_subjects(db_session, partner_id)
    api_client.app.dependency_overrides[require_admin_user] = lambda: {
        "user_id": str(uuid4()),
        "roles": ["NEFT_FINANCE"],
    }

    response = api_client.post(f"/api/core/v1/admin/marketplace/products/{product_id}:approve")

    assert response.status_code == 403


def test_queue_returns_empty_when_marketplace_tables_are_not_bootstrapped() -> None:
    with scoped_session_context(tables=()) as session:
        with router_client_context(
            router=moderation_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: {"user_id": str(uuid4()), "roles": ["admin"]}},
        ) as client:
            response = client.get("/api/core/v1/admin/marketplace/moderation/queue")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
