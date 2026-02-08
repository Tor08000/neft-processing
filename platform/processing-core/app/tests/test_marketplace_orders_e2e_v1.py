from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.marketplace_catalog import MarketplaceService, MarketplaceServiceStatus
from app.models.marketplace_offers import (
    MarketplaceOffer,
    MarketplaceOfferEntitlementScope,
    MarketplaceOfferGeoScope,
    MarketplaceOfferPriceModel,
    MarketplaceOfferStatus,
    MarketplaceOfferSubjectType,
)
from app.models.marketplace_orders import MarketplaceOrderEventType
from app.routers.client_marketplace_orders import router as client_orders_router
from app.routers.partner.marketplace_orders import router as partner_orders_router
from app.routers.admin.marketplace_orders import router as admin_orders_router
from app.security.rbac.principal import Principal, get_principal
from app.api.dependencies.admin import require_admin_user


CURRENT_PRINCIPAL: Principal | None = None


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


def _build_partner_principal(partner_id: str) -> Principal:
    return Principal(
        user_id=UUID(str(uuid4())),
        roles={"partner_user"},
        scopes=set(),
        client_id=None,
        partner_id=UUID(partner_id),
        is_admin=False,
        raw_claims={"user_id": str(uuid4()), "roles": ["partner_user"], "partner_id": partner_id},
    )


def _build_app(session_factory: sessionmaker) -> FastAPI:
    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(client_orders_router, prefix="/api")
    app.include_router(partner_orders_router, prefix="/api")
    app.include_router(admin_orders_router, prefix="/api/v1/admin")

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_get_principal() -> Principal:
        if CURRENT_PRINCIPAL is None:
            raise RuntimeError("principal_not_set")
        return CURRENT_PRINCIPAL

    def override_admin_user():
        return {"user_id": str(uuid4()), "roles": ["ADMIN"]}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_principal] = override_get_principal
    app.dependency_overrides[require_admin_user] = override_admin_user
    return app


def _create_offer(db, partner_id: str) -> MarketplaceOffer:
    service = MarketplaceService(
        id=str(uuid4()),
        partner_id=partner_id,
        title="Diagnostics",
        description="Engine diagnostics",
        category="Auto",
        status=MarketplaceServiceStatus.ACTIVE,
        duration_min=30,
    )
    offer = MarketplaceOffer(
        id=str(uuid4()),
        partner_id=partner_id,
        subject_type=MarketplaceOfferSubjectType.SERVICE,
        subject_id=str(service.id),
        title_override="Diagnostics",
        status=MarketplaceOfferStatus.ACTIVE,
        currency="RUB",
        price_model=MarketplaceOfferPriceModel.FIXED,
        price_amount=1500,
        geo_scope=MarketplaceOfferGeoScope.ALL_PARTNER_LOCATIONS,
        location_ids=[],
        entitlement_scope=MarketplaceOfferEntitlementScope.ALL_CLIENTS,
        allowed_subscription_codes=[],
        allowed_client_ids=[],
    )
    db.add(service)
    db.add(offer)
    db.commit()
    return offer


def test_marketplace_orders_lifecycle_e2e(test_db_sessionmaker: sessionmaker) -> None:
    app = _build_app(test_db_sessionmaker)
    client = TestClient(app)

    client_id = str(uuid4())
    partner_id = str(uuid4())
    with test_db_sessionmaker() as db:
        offer = _create_offer(db, partner_id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    create_response = client.post(
        "/api/v1/marketplace/client/orders",
        json={"items": [{"offer_id": offer.id, "qty": 1}], "payment_method": "NEFT_INTERNAL"},
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["id"]

    pay_response = client.post(
        f"/api/v1/marketplace/client/orders/{order_id}:pay",
        json={"payment_method": "NEFT_INTERNAL"},
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == "PAID"

    CURRENT_PRINCIPAL = _build_partner_principal(partner_id)
    confirm_response = client.post(f"/api/v1/marketplace/partner/orders/{order_id}:confirm", json={})
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "CONFIRMED_BY_PARTNER"

    proof_response = client.post(
        f"/api/v1/marketplace/partner/orders/{order_id}/proofs",
        json={"attachment_id": str(uuid4()), "kind": "PHOTO", "note": "before/after"},
    )
    assert proof_response.status_code == 201

    complete_response = client.post(
        f"/api/v1/marketplace/partner/orders/{order_id}:complete",
        json={"comment": "work done"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "COMPLETED"

    events_response = client.get(f"/api/v1/admin/marketplace/orders/{order_id}/events")
    assert events_response.status_code == 200
    events = events_response.json()
    assert [event["event_type"] for event in events] == [
        MarketplaceOrderEventType.CREATED.value,
        MarketplaceOrderEventType.PAYMENT_PENDING.value,
        MarketplaceOrderEventType.PAYMENT_PAID.value,
        MarketplaceOrderEventType.CONFIRMED.value,
        MarketplaceOrderEventType.COMPLETED.value,
    ]


def test_marketplace_orders_proof_required(test_db_sessionmaker: sessionmaker) -> None:
    app = _build_app(test_db_sessionmaker)
    client = TestClient(app)

    client_id = str(uuid4())
    partner_id = str(uuid4())
    with test_db_sessionmaker() as db:
        offer = _create_offer(db, partner_id)

    global CURRENT_PRINCIPAL
    CURRENT_PRINCIPAL = _build_client_principal(client_id)
    create_response = client.post(
        "/api/v1/marketplace/client/orders",
        json={"items": [{"offer_id": offer.id, "qty": 1}], "payment_method": "NEFT_INTERNAL"},
    )
    order_id = create_response.json()["id"]
    client.post(
        f"/api/v1/marketplace/client/orders/{order_id}:pay",
        json={"payment_method": "NEFT_INTERNAL"},
    )

    CURRENT_PRINCIPAL = _build_partner_principal(partner_id)
    confirm_response = client.post(f"/api/v1/marketplace/partner/orders/{order_id}:confirm", json={})
    assert confirm_response.status_code == 200

    complete_response = client.post(
        f"/api/v1/marketplace/partner/orders/{order_id}:complete",
        json={"comment": "work done"},
    )
    assert complete_response.status_code == 409
