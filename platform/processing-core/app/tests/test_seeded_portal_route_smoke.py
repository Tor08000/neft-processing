from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.client import client_portal_user
from app.api.v1.endpoints.geo_metrics import router as geo_metrics_router
from app.api.v1.endpoints.geo_tiles import router as geo_tiles_router
from app.db import Base, get_db
from app.fastapi_utils import generate_unique_id
from app.models import fuel as fuel_models
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.fuel import FuelNetwork, FuelStation
from app.models.geo_metrics import GeoStationMetricsDaily, GeoTilesDaily, GeoTilesDailyOverlay
from app.models.legal_acceptance import LegalAcceptance
from app.models.legal_document import LegalDocument, LegalDocumentContentType, LegalDocumentStatus
from app.models.marketplace_catalog import MarketplaceProductCard, MarketplaceService
from app.models.marketplace_moderation import MarketplaceModerationAudit
from app.models.marketplace_offers import MarketplaceOffer
from app.routers.admin.legal import router as legal_router
from app.routers.admin.marketplace_moderation import router as moderation_router
from app.routers.client_portal_v1 import router as client_portal_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context

MARKETPLACE_SMOKE_TABLES = (
    AuditLog.__table__,
    MarketplaceModerationAudit.__table__,
    MarketplaceOffer.__table__,
    MarketplaceProductCard.__table__,
    MarketplaceService.__table__,
)

LEGAL_SMOKE_TABLES = (
    AuditLog.__table__,
    LegalDocument.__table__,
    LegalAcceptance.__table__,
)

CLIENT_DASHBOARD_SMOKE_TABLES = (Client.__table__,)

GEO_SMOKE_TABLES = (
    FuelNetwork.__table__,
    FuelStation.__table__,
    GeoStationMetricsDaily.__table__,
    GeoTilesDaily.__table__,
    GeoTilesDailyOverlay.__table__,
)


def _admin_claims(*roles: str) -> dict[str, object]:
    return {
        "user_id": str(uuid4()),
        "sub": str(uuid4()),
        "email": "admin@neft.local",
        "roles": list(roles),
        "role": roles[0] if roles else None,
    }


def _owner_token(*, client_id: str) -> dict[str, object]:
    return {
        "sub": "client-owner-1",
        "user_id": "client-owner-1",
        "subject_type": "client_user",
        "portal": "client",
        "roles": ["CLIENT_OWNER"],
        "role": "CLIENT_OWNER",
        "client_id": client_id,
    }


def _seed_marketplace_subjects(db: Session, partner_id: str) -> tuple[str, str]:
    product = MarketplaceProductCard(
        id=str(uuid4()),
        partner_id=partner_id,
        title="Seeded product",
        description="Product pending review",
        category="fuel",
        status="PENDING_REVIEW",
        tags=[],
        attributes={},
        variants=[],
    )
    service = MarketplaceService(
        id=str(uuid4()),
        partner_id=partner_id,
        title="Seeded service",
        description="Service pending review",
        category="fleet",
        status="PENDING_REVIEW",
        tags=[],
        attributes={},
        duration_min=30,
        requirements=None,
    )
    db.add_all([product, service])
    db.commit()
    return str(product.id), str(service.id)


def _seed_marketplace_offer(db: Session, partner_id: str, subject_id: str) -> None:
    db.add(
        MarketplaceOffer(
            id=str(uuid4()),
            partner_id=partner_id,
            subject_type="PRODUCT",
            subject_id=subject_id,
            title_override="Seeded offer",
            description_override="Offer pending review",
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
    )
    db.commit()


@contextmanager
def _geo_client_context() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine, tables=list(GEO_SMOKE_TABLES))

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(geo_tiles_router, prefix="")
    app.include_router(geo_metrics_router, prefix="")

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, session_local
    finally:
        Base.metadata.drop_all(bind=engine, tables=list(GEO_SMOKE_TABLES))
        engine.dispose()


def test_admin_marketplace_seeded_queue_smoke() -> None:
    with scoped_session_context(tables=MARKETPLACE_SMOKE_TABLES) as session:
        partner_id = str(uuid4())
        product_id, _ = _seed_marketplace_subjects(session, partner_id)
        _seed_marketplace_offer(session, partner_id, product_id)

        with router_client_context(
            router=moderation_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("admin")},
        ) as client:
            response = client.get("/api/core/v1/admin/marketplace/moderation/queue", params={"status": "PENDING_REVIEW"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert {item["type"] for item in payload["items"]} == {"PRODUCT", "SERVICE", "OFFER"}


def test_admin_geo_seeded_route_smoke() -> None:
    with _geo_client_context() as (client, session_local):
        with session_local() as db:
            network = FuelNetwork(
                name="Seeded network",
                provider_code="GN4",
                status=fuel_models.FuelNetworkStatus.ACTIVE,
            )
            db.add(network)
            db.commit()
            db.refresh(network)

            station = FuelStation(
                network_id=str(network.id),
                station_code="A1",
                name="Seeded station",
                city="Moscow",
                lat=55.75,
                lon=37.61,
                status=fuel_models.FuelStationStatus.ACTIVE,
                health_status="OFFLINE",
                risk_zone="RED",
            )
            db.add(station)
            db.commit()
            db.refresh(station)

            db.add(
                GeoStationMetricsDaily(
                    day=date(2026, 2, 12),
                    station_id=str(station.id),
                    tx_count=7,
                    captured_count=6,
                    declined_count=1,
                    amount_sum=Decimal("210.50"),
                    liters_sum=Decimal("40.500"),
                    risk_red_count=3,
                    risk_yellow_count=1,
                )
            )
            db.add(
                GeoTilesDaily(
                    day=date(2026, 2, 12),
                    zoom=10,
                    tile_x=619,
                    tile_y=320,
                    tx_count=7,
                    amount_sum=Decimal("210.50"),
                )
            )
            db.add(
                GeoTilesDailyOverlay(
                    day=date(2026, 2, 12),
                    zoom=10,
                    tile_x=619,
                    tile_y=320,
                    overlay_kind="RISK_RED",
                    value=3,
                )
            )
            db.commit()

        tiles_response = client.get(
            "/api/v1/geo/tiles?date_from=2026-02-12&date_to=2026-02-12&min_lat=55.70&min_lon=37.50&max_lat=55.80&max_lon=37.70&zoom=10&metric=tx_count&limit_tiles=2000"
        )
        overlays_response = client.get(
            "/api/v1/geo/tiles/overlays?date_from=2026-02-12&date_to=2026-02-12&min_lat=55.70&min_lon=37.50&max_lat=55.80&max_lon=37.70&zoom=10&overlay_kind=RISK_RED&limit_tiles=2000"
        )
        metrics_response = client.get(
            "/api/v1/geo/stations/metrics?date_from=2026-02-12&date_to=2026-02-12&metric=tx_count&limit=20"
        )

    assert tiles_response.status_code == 200
    assert tiles_response.json()["returned_tiles"] == 1
    assert overlays_response.status_code == 200
    assert overlays_response.json()["returned_tiles"] == 1
    assert metrics_response.status_code == 200
    assert metrics_response.json()["items"][0]["station_name"] == "Seeded station"


def test_admin_legal_seeded_registry_smoke() -> None:
    with scoped_session_context(tables=LEGAL_SMOKE_TABLES) as session:
        session.add(
            LegalDocument(
                id=str(uuid4()),
                code="LEGAL_TERMS",
                version="1",
                title="Legal terms",
                locale="ru",
                effective_from=datetime.now(timezone.utc) - timedelta(days=1),
                status=LegalDocumentStatus.PUBLISHED,
                content_type=LegalDocumentContentType.MARKDOWN,
                content="seeded legal content",
                content_hash="hash-legal-terms-v1",
                published_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        session.commit()

        with router_client_context(
            router=legal_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_LEGAL")},
        ) as client:
            response = client.get("/api/core/v1/admin/legal/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["code"] == "LEGAL_TERMS"
    assert payload["items"][0]["status"] == "PUBLISHED"


def test_client_dashboard_seeded_bootstrap_smoke() -> None:
    client_id = str(uuid4())
    with scoped_session_context(tables=CLIENT_DASHBOARD_SMOKE_TABLES) as session:
        session.add(Client(id=UUID(client_id), name="Seeded Client", status="ONBOARDING"))
        session.commit()

        with router_client_context(
            router=client_portal_router,
            prefix="/api/core",
            db_session=session,
            dependency_overrides={client_portal_user: lambda: _owner_token(client_id=client_id)},
        ) as client:
            response = client.get("/api/core/client/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "OWNER"
    assert [item["key"] for item in payload["widgets"]] == [
        "total_spend_30d",
        "transactions_30d",
        "spend_timeseries_30d",
        "top_cards",
        "health_exports_email",
        "support_overview",
        "slo_health",
        "owner_actions",
    ]
