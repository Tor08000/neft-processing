from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.routers.admin.fraud import router as fraud_router

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_user)])
router.include_router(fraud_router)

__all__ = ["router"]
