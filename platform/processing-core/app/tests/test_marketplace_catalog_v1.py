from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductCard, MarketplaceProductCardStatus
from app.routers.marketplace_catalog import router as catalog_router
from app.routers.partner.marketplace_catalog import router as partner_router
from app.security.client_auth import require_client_user
from app.security.rbac.principal import Principal, get_principal
from app.services.marketplace_catalog_service import MarketplaceCatalogService

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
    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(partner_router, prefix="/api")
    app.include_router(catalog_router, prefix="/api")

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

    with TestClient(app) as client:
        yield client, test_db_sessionmaker


@pytest.fixture(autouse=True)
def _cleanup_cards(test_db_session):
    test_db_session.query(MarketplaceProductCard).delete()
    test_db_session.commit()


def _create_product_payload() -> dict:
    return {
        "title": "Diagnostics",
        "description": "Full engine diagnostics",
        "category": "Auto",
        "tags": ["engine", "inspection"],
        "attributes": {"brand": "Acme"},
        "variants": [{"name": "Base", "sku": "DX-1", "props": {"duration": "2h"}}],
    }


def test_product_create_update_get(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    assert response.status_code == 201
    product_id = response.json()["id"]

    update_payload = {"title": "Diagnostics+", "attributes": {"brand": "Acme", "model": "X"}}
    update_response = client.patch(f"/api/partner/products/{product_id}", json=update_payload)
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Diagnostics+"

    get_response = client.get(f"/api/partner/products/{product_id}")
    assert get_response.status_code == 200
    assert get_response.json()["attributes"]["model"] == "X"


def test_status_transitions(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    product_id = response.json()["id"]

    submit_response = client.post(f"/api/partner/products/{product_id}/submit")
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "PENDING_REVIEW"

    archive_response = client.post(f"/api/partner/products/{product_id}/archive")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "ARCHIVED"


def test_partner_cannot_access_foreign_product(api_client: tuple[TestClient, sessionmaker]):
    client, _ = api_client
    partner_id = str(uuid4())
    other_partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    product_id = response.json()["id"]

    CURRENT_PRINCIPAL = _build_principal(other_partner_id)
    get_response = client.get(f"/api/partner/products/{product_id}")
    assert get_response.status_code == 403

    update_response = client.patch(f"/api/partner/products/{product_id}", json={"title": "Hack"})
    assert update_response.status_code == 403


def test_client_catalog_active_only(api_client: tuple[TestClient, sessionmaker], test_db_session):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    active_id = response.json()["id"]

    response_draft = client.post("/api/partner/products", json=_create_product_payload())
    draft_id = response_draft.json()["id"]

    product = test_db_session.query(MarketplaceProductCard).filter(MarketplaceProductCard.id == active_id).one()
    product.status = MarketplaceProductCardStatus.ACTIVE
    test_db_session.commit()

    list_response = client.get("/api/marketplace/catalog/products")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    ids = {item["id"] for item in items}
    assert active_id in ids
    assert draft_id not in ids


def test_submit_requires_draft(api_client: tuple[TestClient, sessionmaker], test_db_session):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    product_id = response.json()["id"]

    product = test_db_session.query(MarketplaceProductCard).filter(MarketplaceProductCard.id == product_id).one()
    product.status = MarketplaceProductCardStatus.ACTIVE
    test_db_session.commit()

    submit_response = client.post(f"/api/partner/products/{product_id}/submit")
    assert submit_response.status_code == 409
    assert submit_response.json()["detail"]["error"] == "PRODUCT_CARD_STATE_INVALID"


def test_patch_active_forbidden(api_client: tuple[TestClient, sessionmaker], test_db_session):
    client, _ = api_client
    partner_id = str(uuid4())
    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_principal(partner_id)

    response = client.post("/api/partner/products", json=_create_product_payload())
    product_id = response.json()["id"]

    product = test_db_session.query(MarketplaceProductCard).filter(MarketplaceProductCard.id == product_id).one()
    product.status = MarketplaceProductCardStatus.ACTIVE
    test_db_session.commit()

    update_response = client.patch(f"/api/partner/products/{product_id}", json={"title": "Updated"})
    assert update_response.status_code == 409
    assert update_response.json()["detail"]["error"] == "INVALID_STATE"


def test_approve_requires_admin_role(test_db_session):
    service = MarketplaceCatalogService(test_db_session)
    product = service.create_product_card(partner_id=str(uuid4()), payload=_create_product_payload())
    test_db_session.commit()

    service.submit_product_card(product=product)
    test_db_session.commit()

    with pytest.raises(ValueError, match="PRODUCT_CARD_STATE_INVALID"):
        service.approve_product_card(product=product, actor_role="partner")

    service.approve_product_card(product=product, actor_role="admin")
    test_db_session.commit()
    assert product.status == MarketplaceProductCardStatus.ACTIVE
