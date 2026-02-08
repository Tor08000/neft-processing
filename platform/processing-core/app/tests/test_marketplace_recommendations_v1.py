from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.redis import get_redis
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.marketplace_catalog import MarketplaceProductCard
from app.models.marketplace_client_events import (
    MarketplaceClientEntityType,
    MarketplaceClientEvent,
    MarketplaceClientEventSource,
    MarketplaceClientEventType,
)
from app.models.marketplace_offers import MarketplaceOffer
from app.routers.client.marketplace_recommendations import router as recommendations_router
from app.security.client_auth import require_client_user

CURRENT_CLIENT_TOKEN: dict = {
    "client_id": str(uuid4()),
    "user_id": str(uuid4()),
    "subscription_codes": ["PRO"],
    "region_code": "RU-MOW",
}


@pytest.fixture()
def api_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        MarketplaceProductCard.__table__,
        MarketplaceOffer.__table__,
        MarketplaceClientEvent.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(recommendations_router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: None
    app.dependency_overrides[require_client_user] = lambda: CURRENT_CLIENT_TOKEN

    with TestClient(app) as client:
        yield client, SessionLocal

    for table in reversed(tables):
        table.drop(bind=engine)
    engine.dispose()


def _create_product_card(db: Session, *, category: str, title: str) -> MarketplaceProductCard:
    product = MarketplaceProductCard(
        id=str(uuid4()),
        partner_id=str(uuid4()),
        title=title,
        description=f"{title} description",
        category=category,
        status="PUBLISHED",
        tags=[],
        attributes={},
        variants=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(product)
    db.commit()
    return product


def _create_offer(db: Session, *, product: MarketplaceProductCard, status: str = "ACTIVE") -> MarketplaceOffer:
    offer = MarketplaceOffer(
        id=str(uuid4()),
        partner_id=str(uuid4()),
        subject_type="PRODUCT",
        subject_id=str(product.id),
        title_override=None,
        description_override=None,
        status=status,
        moderation_comment=None,
        currency="RUB",
        price_model="FIXED",
        price_amount=1500,
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
        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
        valid_to=datetime.now(timezone.utc) + timedelta(days=10),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(offer)
    db.commit()
    return offer


def test_recommendations_rank_recent_views(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    client_id = CURRENT_CLIENT_TOKEN["client_id"]

    with SessionLocal() as db:
        product_a = _create_product_card(db, category="Auto", title="Diagnostics")
        product_b = _create_product_card(db, category="Auto", title="Wash")
        offer_a = _create_offer(db, product=product_a)
        offer_b = _create_offer(db, product=product_b)
        event = MarketplaceClientEvent(
            client_id=client_id,
            tenant_id=None,
            user_id=str(uuid4()),
            session_id="session-1",
            event_type=MarketplaceClientEventType.OFFER_VIEWED,
            entity_type=MarketplaceClientEntityType.PRODUCT,
            entity_id=str(product_a.id),
            source=MarketplaceClientEventSource.CLIENT_PORTAL,
            page="/marketplace",
            payload={"category": "Auto"},
        )
        db.add(event)
        db.commit()

    response = client.get("/api/v1/marketplace/client/recommendations?limit=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["offer_id"] == str(offer_a.id)
    assert {item["offer_id"] for item in payload["items"]} == {str(offer_a.id), str(offer_b.id)}


def test_recommendations_filters_status_and_entitlements(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client

    with SessionLocal() as db:
        product = _create_product_card(db, category="Auto", title="Oil change")
        offer_active = _create_offer(db, product=product, status="ACTIVE")
        _create_offer(db, product=product, status="DRAFT")
        restricted = _create_offer(db, product=product, status="ACTIVE")
        restricted.entitlement_scope = "SEGMENT_ONLY"
        restricted.allowed_client_ids = [str(uuid4())]
        restricted.valid_to = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

    response = client.get("/api/v1/marketplace/client/recommendations?limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert [item["offer_id"] for item in payload["items"]] == [str(offer_active.id)]


def test_recommendations_why(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    client_id = CURRENT_CLIENT_TOKEN["client_id"]

    with SessionLocal() as db:
        product = _create_product_card(db, category="Auto", title="Diagnostics")
        offer = _create_offer(db, product=product)
        event = MarketplaceClientEvent(
            client_id=client_id,
            tenant_id=None,
            user_id=str(uuid4()),
            session_id="session-1",
            event_type=MarketplaceClientEventType.OFFER_VIEWED,
            entity_type=MarketplaceClientEntityType.PRODUCT,
            entity_id=str(product.id),
            source=MarketplaceClientEventSource.CLIENT_PORTAL,
            page="/marketplace",
            payload={"category": "Auto"},
        )
        db.add(event)
        db.commit()

    response = client.get(f"/api/v1/marketplace/client/recommendations/why?offer_id={offer.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["offer_id"] == str(offer.id)
    assert payload["reasons"]
