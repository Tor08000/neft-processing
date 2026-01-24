from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.admin import require_admin_user
from app.schemas.admin.runtime_summary import RuntimeSummaryResponse
from app.services.admin_runtime import build_runtime_summary


router = APIRouter(prefix="/admin/runtime", tags=["admin-runtime"], dependencies=[Depends(require_admin_user)])


@router.get("/summary", response_model=RuntimeSummaryResponse)
def runtime_summary() -> RuntimeSummaryResponse:
    return build_runtime_summary()


__all__ = ["router"]
