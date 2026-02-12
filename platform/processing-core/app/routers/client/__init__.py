from __future__ import annotations

from fastapi import APIRouter

from app.routers.client.marketplace_recommendations import router as marketplace_recommendations_router
from app.routers.client_marketplace import router as marketplace_router
from app.routers.client_marketplace_deals import router as marketplace_deals_router
from app.routers.client_marketplace_orders import router as marketplace_orders_router
from app.routers.legal import router as legal_router
from app.routers.marketplace_client_events import router as marketplace_events_router

router = APIRouter(prefix="/v1")

router.include_router(marketplace_router)
router.include_router(marketplace_deals_router)
router.include_router(marketplace_orders_router)
router.include_router(marketplace_events_router)
router.include_router(marketplace_recommendations_router)
router.include_router(legal_router)

__all__ = ["router"]
