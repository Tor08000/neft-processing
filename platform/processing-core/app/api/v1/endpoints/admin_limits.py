from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.routers.admin.limits import router as limits_router


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_user)])
router.include_router(limits_router)

__all__ = ["router"]
