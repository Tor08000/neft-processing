from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductCard, MarketplaceService
from app.models.marketplace_moderation import MarketplaceModerationAudit, MarketplaceModerationEntityType
from app.models.marketplace_offers import MarketplaceOffer
from app.routers.admin.marketplace_moderation import router as moderation_router


@pytest.fixture()
def api_client(test_db_sessionmaker) -> tuple[TestClient, sessionmaker]:
    app = FastAPI()
    app.include_router(moderation_router, prefix="/api/v1/admin")

    def override_get_db():
        db = test_db_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_user] = lambda: {"user_id": str(uuid4()), "roles": ["admin"]}

    with TestClient(app) as client:
        yield client, test_db_sessionmaker


@pytest.fixture(autouse=True)
def _cleanup_tables(test_db_session: Session):
    test_db_session.query(MarketplaceModerationAudit).delete()
    test_db_session.query(MarketplaceOffer).delete()
    test_db_session.query(MarketplaceProductCard).delete()
    test_db_session.query(MarketplaceService).delete()
    test_db_session.commit()


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


def test_queue_returns_pending_items(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    product_id, _ = _seed_subjects(test_db_session, partner_id)
    _seed_offer(test_db_session, partner_id, product_id)

    response = client.get("/api/v1/admin/marketplace/moderation/queue", params={"status": "PENDING_REVIEW"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    types = {item["type"] for item in payload["items"]}
    assert types == {"PRODUCT", "SERVICE", "OFFER"}


def test_approve_transitions_product_card(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    product_id, _ = _seed_subjects(test_db_session, partner_id)

    response = client.post(f"/api/v1/admin/marketplace/products/{product_id}:approve")
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"

    card = test_db_session.query(MarketplaceProductCard).filter(MarketplaceProductCard.id == product_id).one()
    assert card.status == "ACTIVE"


def test_reject_offer_creates_audit(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    product_id, _ = _seed_subjects(test_db_session, partner_id)
    offer = _seed_offer(test_db_session, partner_id, product_id)

    response = client.post(
        f"/api/v1/admin/marketplace/offers/{offer.id}:reject",
        json={"reason_code": "MISSING_INFO", "comment": "Missing details"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DRAFT"

    audit = (
        test_db_session.query(MarketplaceModerationAudit)
        .filter(
            MarketplaceModerationAudit.entity_type == MarketplaceModerationEntityType.OFFER,
            MarketplaceModerationAudit.entity_id == str(offer.id),
        )
        .one()
    )
    assert audit.action.value == "REJECT"
    assert audit.reason_code == "MISSING_INFO"
    assert audit.comment == "Missing details"
