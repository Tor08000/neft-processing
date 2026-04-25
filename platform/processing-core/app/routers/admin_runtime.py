from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.admin_capability import require_admin_capability
from app.db import get_db
from app.schemas.admin.runtime_summary import RuntimeSummaryResponse
from app.services.admin_runtime import build_runtime_summary


router = APIRouter(
    prefix="/v1/admin/runtime",
    tags=["admin-runtime"],
    dependencies=[Depends(require_admin_capability("runtime"))],
)


@router.get("/summary", response_model=RuntimeSummaryResponse)
def runtime_summary(db: Session = Depends(get_db)) -> RuntimeSummaryResponse:
    return build_runtime_summary(db)


__all__ = ["router"]
