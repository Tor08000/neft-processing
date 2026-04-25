from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.models.marketplace_catalog import (
    MarketplacePriceModel,
    MarketplaceProduct,
    MarketplaceProductModerationStatus,
    MarketplaceProductStatus,
    MarketplaceProductType,
    PartnerProfile,
    PartnerVerificationStatus,
)
from app.models.marketplace_offers import (
    MarketplaceOffer,
    MarketplaceOfferEntitlementScope,
    MarketplaceOfferGeoScope,
    MarketplaceOfferPriceModel,
    MarketplaceOfferStatus,
    MarketplaceOfferSubjectType,
)
from app.models.marketplace_sponsored import SponsoredCampaign
from app.models.subscriptions_v1 import (
    ClientSubscription,
    SubscriptionModuleCode,
    SubscriptionPlan,
    SubscriptionPlanLimit,
    SubscriptionPlanModule,
    SubscriptionStatus,
)
from app.routers.client_marketplace import router as client_marketplace_router
from app.security.client_auth import require_client_user
from app.services import entitlements_service

CURRENT_TOKEN: dict | None = None


@pytest.fixture(autouse=True)
def _prepare_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    entitlements_service._ENTITLEMENTS_CACHE.clear()
    monkeypatch.setattr(entitlements_service, "DB_SCHEMA", None, raising=False)
    yield
    entitlements_service._ENTITLEMENTS_CACHE.clear()


def _build_app(*, include_subscription_tables: bool = False) -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    tables = [
        PartnerProfile.__table__,
        MarketplaceProduct.__table__,
        MarketplaceOffer.__table__,
        SponsoredCampaign.__table__,
    ]
    if include_subscription_tables:
        tables = [
            SubscriptionPlan.__table__,
            SubscriptionPlanModule.__table__,
            SubscriptionPlanLimit.__table__,
            ClientSubscription.__table__,
            *tables,
        ]

    for table in tables:
        table.create(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(client_marketplace_router, prefix="/api/v1")

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
    app.dependency_overrides[require_client_user] = override_require_client_user
    return TestClient(app), SessionLocal


def _token_for_client(client_id: str) -> dict:
    return {"client_id": client_id, "user_id": str(uuid4()), "tenant_id": str(uuid4())}


def _seed_marketplace_subscription(db, *, client_id: str, enabled: bool) -> None:
    plan_id = f"plan-{uuid4()}"
    db.add(SubscriptionPlan(id=plan_id, code=f"PLAN_{uuid4().hex[:8].upper()}", title="Marketplace plan", is_active=True))
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


def _seed_partner_profile(db, *, partner_id: str, company_name: str, verified: bool = True) -> None:
    profile = PartnerProfile(
        id=str(uuid4()),
        partner_id=partner_id,
        company_name=company_name,
        description="Trusted marketplace partner",
        verification_status=PartnerVerificationStatus.VERIFIED if verified else PartnerVerificationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(profile)


def _seed_product(
    db,
    *,
    partner_id: str,
    title: str,
    description: str,
    category: str,
    price_model: MarketplacePriceModel,
    price_config: dict,
    product_type: MarketplaceProductType = MarketplaceProductType.SERVICE,
) -> str:
    product_id = str(uuid4())
    product = MarketplaceProduct(
        id=product_id,
        partner_id=partner_id,
        type=product_type,
        title=title,
        description=description,
        category=category,
        price_model=price_model,
        price_config=price_config,
        status=MarketplaceProductStatus.PUBLISHED,
        moderation_status=MarketplaceProductModerationStatus.APPROVED,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc),
    )
    db.add(product)
    db.commit()
    return product_id


def _seed_offer(
    db,
    *,
    partner_id: str,
    subject_id: str,
    subject_type: MarketplaceOfferSubjectType,
    title_override: str = "Приоритетный слот",
) -> str:
    offer_id = str(uuid4())
    offer = MarketplaceOffer(
        id=offer_id,
        partner_id=partner_id,
        subject_type=subject_type,
        subject_id=subject_id,
        title_override=title_override,
        description_override="Быстрое оформление",
        status=MarketplaceOfferStatus.ACTIVE,
        moderation_comment=None,
        currency="RUB",
        price_model=MarketplaceOfferPriceModel.FIXED,
        price_amount=8900,
        price_min=None,
        price_max=None,
        vat_rate=None,
        terms={"min_qty": 1, "max_qty": 1},
        geo_scope=MarketplaceOfferGeoScope.ALL_PARTNER_LOCATIONS,
        location_ids=[],
        region_code=None,
        entitlement_scope=MarketplaceOfferEntitlementScope.ALL_CLIENTS,
        allowed_subscription_codes=[],
        allowed_client_ids=[],
        valid_from=None,
        valid_to=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(offer)
    db.commit()
    return offer_id


def test_client_marketplace_products_list_returns_live_card_fields() -> None:
    global CURRENT_TOKEN
    client, SessionLocal = _build_app()
    CURRENT_TOKEN = _token_for_client(str(uuid4()))
    category = f"client-marketplace-{uuid4()}"
    partner_id = str(uuid4())

    with SessionLocal() as db:
        _seed_partner_profile(db, partner_id=partner_id, company_name="ООО Диагностика")
        _seed_product(
            db,
            partner_id=partner_id,
            title="Диагностика двигателя",
            description="Полная диагностика двигателя за один визит.",
            category=category,
            price_model=MarketplacePriceModel.FIXED,
            price_config={"amount": 12000, "currency": "RUB"},
        )

    response = client.get(
        "/api/v1/client/marketplace/products",
        params={"category": category, "type": "SERVICE", "q": "двигателя"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["partner_name"] == "ООО Диагностика"
    assert item["short_description"] == "Полная диагностика двигателя за один визит."
    assert item["price_summary"] == "12 000 ₽"
    assert item["type"] == "SERVICE"
    client.close()


def test_client_marketplace_product_detail_returns_partner_and_price_summary() -> None:
    global CURRENT_TOKEN
    client, SessionLocal = _build_app()
    CURRENT_TOKEN = _token_for_client(str(uuid4()))
    partner_id = str(uuid4())

    with SessionLocal() as db:
        _seed_partner_profile(db, partner_id=partner_id, company_name="Сервис Плюс")
        product_id = _seed_product(
            db,
            partner_id=partner_id,
            title="Почасовой сервис",
            description="Техническая помощь по запросу.",
            category=f"client-marketplace-{uuid4()}",
            price_model=MarketplacePriceModel.PER_UNIT,
            price_config={"amount_per_unit": 950, "unit": "hour", "currency": "RUB"},
        )

    response = client.get(f"/api/v1/client/marketplace/products/{product_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["partner"] == {
        "id": partner_id,
        "company_name": "Сервис Плюс",
        "verified": True,
    }
    assert payload["price_summary"] == "950 ₽ / hour"
    assert payload["sla_summary"] == {"obligations": [], "penalties": None}
    client.close()


def test_client_marketplace_product_offers_returns_subject_filtered_live_offers() -> None:
    global CURRENT_TOKEN
    client, SessionLocal = _build_app()
    CURRENT_TOKEN = _token_for_client(str(uuid4()))
    partner_id = str(uuid4())

    with SessionLocal() as db:
        _seed_partner_profile(db, partner_id=partner_id, company_name="Сервис Плюс")
        product_id = _seed_product(
            db,
            partner_id=partner_id,
            title="Выездная диагностика",
            description="Диагностика на месте.",
            category=f"client-marketplace-{uuid4()}",
            price_model=MarketplacePriceModel.FIXED,
            price_config={"amount": 8900, "currency": "RUB"},
            product_type=MarketplaceProductType.SERVICE,
        )
        offer_id = _seed_offer(
            db,
            partner_id=partner_id,
            subject_id=product_id,
            subject_type=MarketplaceOfferSubjectType.SERVICE,
            title_override="Приоритетный слот",
        )

    response = client.get(f"/api/v1/client/marketplace/products/{product_id}/offers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"] == [
        {
            "id": offer_id,
            "subject_type": "SERVICE",
            "subject_id": product_id,
            "title": "Приоритетный слот",
            "currency": "RUB",
            "price_model": "FIXED",
            "price_amount": 8900.0,
            "price_min": None,
            "price_max": None,
            "geo_scope": "ALL_PARTNER_LOCATIONS",
            "location_ids": [],
            "terms": {"min_qty": 1, "max_qty": 1},
            "valid_from": None,
            "valid_to": None,
        }
    ]
    client.close()


def test_client_marketplace_products_require_marketplace_module_when_entitlements_are_present() -> None:
    global CURRENT_TOKEN
    client, SessionLocal = _build_app(include_subscription_tables=True)
    client_id = str(uuid4())
    CURRENT_TOKEN = _token_for_client(client_id)

    with SessionLocal() as db:
        _seed_marketplace_subscription(db, client_id=client_id, enabled=False)

    response = client.get("/api/v1/client/marketplace/products")
    assert response.status_code == 403
    assert response.json() == {"detail": "feature_not_included"}
    client.close()
