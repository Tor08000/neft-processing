from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProduct
from app.models.marketplace_recommendations import MarketplaceEvent, OfferCandidate, ProductAttributes
from app.routers.client_marketplace import router as client_router
from app.security.client_auth import require_client_user

CURRENT_CLIENT_TOKEN: dict = {"client_id": str(uuid4()), "user_id": str(uuid4())}


@pytest.fixture()
def api_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        MarketplaceProduct.__table__,
        MarketplaceEvent.__table__,
        OfferCandidate.__table__,
        ProductAttributes.__table__,
    ]
    for table in tables:
        table.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(client_router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_client_user] = lambda: CURRENT_CLIENT_TOKEN

    with TestClient(app) as client:
        yield client, SessionLocal

    for table in reversed(tables):
        table.drop(bind=engine)
    engine.dispose()


def _create_product(db: Session, *, category: str, title: str) -> MarketplaceProduct:
    product = MarketplaceProduct(
        id=str(uuid4()),
        partner_id=str(uuid4()),
        type="SERVICE",
        title=title,
        description="Service description",
        category=category,
        price_model="FIXED",
        price_config={"amount": 1500, "currency": "RUB"},
        status="PUBLISHED",
        moderation_status="APPROVED",
        published_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(product)
    db.commit()
    return product


def test_recommendations_and_events(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client
    client_id = CURRENT_CLIENT_TOKEN["client_id"]

    with SessionLocal() as db:
        product = _create_product(db, category="OILS", title="Diesel oil 5W-40")
        candidate = OfferCandidate(
            tenant_id=None,
            client_id=client_id,
            product_id=str(product.id),
            partner_id=str(product.partner_id),
            base_score=0.82,
            reasons=[{"code": "FUEL_MIX_DIESEL", "text": "Вы часто используете дизель"}],
            valid_from=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(candidate)
        db.commit()

    response = client.get("/api/client/marketplace/recommendations?limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["items"][0]["reasons"]

    event_response = client.post(
        "/api/client/marketplace/events",
        json={"event_type": "CLICK", "product_id": str(product.id), "context": {"placement": "home"}},
    )
    assert event_response.status_code == 201
    event_payload = event_response.json()
    assert event_payload["event_type"] == "CLICK"


def test_related_products(api_client: tuple[TestClient, sessionmaker]):
    client, SessionLocal = api_client

    with SessionLocal() as db:
        product = _create_product(db, category="OILS", title="Oil A")
        related = _create_product(db, category="OILS", title="Oil B")
        db.add(
            ProductAttributes(
                product_id=str(product.id),
                partner_id=str(product.partner_id),
                category_code="OILS",
                tags=["diesel"],
            )
        )
        db.add(
            ProductAttributes(
                product_id=str(related.id),
                partner_id=str(related.partner_id),
                category_code="OILS",
                tags=["diesel"],
            )
        )
        db.commit()

    response = client.get(f"/api/client/marketplace/products/{product.id}/related?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert any(item["id"] == str(related.id) for item in payload["items"])