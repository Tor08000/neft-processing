from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductCard, MarketplaceService
from app.models.marketplace_offers import MarketplaceOffer, MarketplaceOfferStatus
from app.routers.admin.marketplace_moderation import router as moderation_router
from app.routers.marketplace_catalog import router as catalog_router
from app.routers.partner.marketplace_offers import router as partner_router
from app.security.client_auth import require_client_user
from app.security.rbac.principal import Principal, get_principal

CURRENT_PRINCIPAL: Principal | None = None
CURRENT_CLIENT_TOKEN: dict = {"client_id": str(uuid4())}


def _build_principal(partner_id: str) -> Principal:
    return Principal(
        user_id=UUID(str(uuid4())),
        roles={"partner_user"},
        scopes=set(),
        client_id=None,
        partner_id=UUID(partner_id),
        is_admin=False,
        raw_claims={"user_id": str(uuid4()), "roles": ["partner_user"], "partner_id": partner_id},
    )


@pytest.fixture()
def api_client(test_db_sessionmaker) -> tuple[TestClient, sessionmaker]:
    app = FastAPI()
    app.include_router(partner_router, prefix="/api")
    app.include_router(catalog_router, prefix="/api")
    app.include_router(moderation_router, prefix="/api")

    def override_get_db():
        db = test_db_sessionmaker()
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
    app.dependency_overrides[require_client_user] = lambda: CURRENT_CLIENT_TOKEN
    app.dependency_overrides[require_admin_user] = lambda: {"admin": True}

    with TestClient(app) as client:
        yield client, test_db_sessionmaker


@pytest.fixture(autouse=True)
def _cleanup_offers(test_db_session):
    test_db_session.query(MarketplaceOffer).delete()
    test_db_session.query(MarketplaceProductCard).delete()
    test_db_session.query(MarketplaceService).delete()
    test_db_session.commit()


def _seed_subjects(db: Session, partner_id: str) -> tuple[str, str]:
    product = MarketplaceProductCard(
        id=str(uuid4()),
        partner_id=partner_id,
        title="Товар",
        description="Описание",
        category="Категория",
        status="DRAFT",
        tags=[],
        attributes={},
        variants=[],
    )
    service = MarketplaceService(
        id=str(uuid4()),
        partner_id=partner_id,
        title="Услуга",
        description="Описание",
        category="Категория",
        status="DRAFT",
        tags=[],
        attributes={},
        duration_min=30,
        requirements=None,
    )
    db.add(product)
    db.add(service)
    db.commit()
    return str(product.id), str(service.id)


def _offer_payload(subject_id: str) -> dict:
    return {
        "subject_type": "PRODUCT",
        "subject_id": subject_id,
        "currency": "RUB",
        "price_model": "FIXED",
        "price_amount": 100,
        "terms": {"min_qty": 1, "max_qty": 5},
        "geo_scope": "ALL_PARTNER_LOCATIONS",
        "entitlement_scope": "ALL_CLIENTS",
    }


def test_partner_create_offer_draft(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)
    product_id, _ = _seed_subjects(test_db_session, partner_id)

    response = client.post("/api/marketplace/partner/offers", json=_offer_payload(product_id))
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"


def test_patch_allowed_only_in_draft(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)
    product_id, _ = _seed_subjects(test_db_session, partner_id)

    response = client.post("/api/marketplace/partner/offers", json=_offer_payload(product_id))
    offer_id = response.json()["id"]

    patch_response = client.patch(
        f"/api/marketplace/partner/offers/{offer_id}",
        json={"title_override": "Новый заголовок"},
    )
    assert patch_response.status_code == 200

    offer = test_db_session.query(MarketplaceOffer).filter(MarketplaceOffer.id == offer_id).one()
    offer.status = MarketplaceOfferStatus.ACTIVE
    test_db_session.commit()

    locked_response = client.patch(
        f"/api/marketplace/partner/offers/{offer_id}",
        json={"title_override": "Запрещено"},
    )
    assert locked_response.status_code == 409
    assert locked_response.json()["detail"]["error"] == "INVALID_STATE"


def test_submit_and_approve_offer(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)
    product_id, _ = _seed_subjects(test_db_session, partner_id)

    response = client.post("/api/marketplace/partner/offers", json=_offer_payload(product_id))
    offer_id = response.json()["id"]

    submit_response = client.post(f"/api/marketplace/partner/offers/{offer_id}:submit")
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "PENDING_REVIEW"

    approve_response = client.post(f"/api/marketplace/moderation/offers/{offer_id}:approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "ACTIVE"


def test_public_catalog_active_only(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)
    product_id, _ = _seed_subjects(test_db_session, partner_id)

    active_response = client.post("/api/marketplace/partner/offers", json=_offer_payload(product_id))
    active_id = active_response.json()["id"]
    draft_response = client.post("/api/marketplace/partner/offers", json=_offer_payload(product_id))
    draft_id = draft_response.json()["id"]

    offer = test_db_session.query(MarketplaceOffer).filter(MarketplaceOffer.id == active_id).one()
    offer.status = MarketplaceOfferStatus.ACTIVE
    test_db_session.commit()

    list_response = client.get("/api/marketplace/catalog/offers")
    assert list_response.status_code == 200
    ids = {item["id"] for item in list_response.json()["items"]}
    assert active_id in ids
    assert draft_id not in ids


def test_entitlements_filter(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)
    product_id, _ = _seed_subjects(test_db_session, partner_id)

    payload = _offer_payload(product_id)
    payload.update({
        "entitlement_scope": "SUBSCRIPTION_ONLY",
        "allowed_subscription_codes": ["PRO"],
    })
    response = client.post("/api/marketplace/partner/offers", json=payload)
    offer_id = response.json()["id"]

    offer = test_db_session.query(MarketplaceOffer).filter(MarketplaceOffer.id == offer_id).one()
    offer.status = MarketplaceOfferStatus.ACTIVE
    test_db_session.commit()

    global CURRENT_CLIENT_TOKEN
    CURRENT_CLIENT_TOKEN = {"client_id": str(uuid4())}

    list_response = client.get("/api/marketplace/catalog/offers")
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []


def test_geo_scope_selected_locations(api_client: tuple[TestClient, sessionmaker], test_db_session: Session) -> None:
    client, _ = api_client
    partner_id = str(uuid4())
    location_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)
    product_id, _ = _seed_subjects(test_db_session, partner_id)

    payload = _offer_payload(product_id)
    payload.update({
        "geo_scope": "SELECTED_LOCATIONS",
        "location_ids": [location_id],
    })
    response = client.post("/api/marketplace/partner/offers", json=payload)
    offer_id = response.json()["id"]

    offer = test_db_session.query(MarketplaceOffer).filter(MarketplaceOffer.id == offer_id).one()
    offer.status = MarketplaceOfferStatus.ACTIVE
    test_db_session.commit()

    list_response = client.get(f"/api/marketplace/catalog/offers?geo={location_id}")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == offer_id

    miss_response = client.get("/api/marketplace/catalog/offers?geo=missing")
    assert miss_response.status_code == 200
    assert miss_response.json()["items"] == []
