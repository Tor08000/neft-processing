from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.routers.admin import (
    accounts,
    billing,
    clearing,
    dashboard,
    integration_monitoring,
    limits,
    merchants,
    operations,
    risk_rules,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_user)])

router.include_router(accounts.router)
router.include_router(limits.router)
router.include_router(operations.router)
router.include_router(dashboard.router)
router.include_router(merchants.router)
router.include_router(clearing.router)
router.include_router(billing.router)
router.include_router(risk_rules.router)
router.include_router(integration_monitoring.router)

__all__ = ["router"]
