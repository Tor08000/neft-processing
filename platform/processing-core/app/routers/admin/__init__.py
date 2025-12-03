from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.routers.admin import billing, clearing, dashboard, limits, merchants, operations

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_user)])

router.include_router(limits.router)
router.include_router(operations.router)
router.include_router(dashboard.router)
router.include_router(merchants.router)
router.include_router(clearing.router)
router.include_router(billing.router)

__all__ = ["router"]
