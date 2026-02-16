from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.routers.admin.partners_v1 import router as partners_router

router = APIRouter(prefix="/admin", tags=["admin-partners"], dependencies=[Depends(require_admin_user)])
router.include_router(partners_router)
