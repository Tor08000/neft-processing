from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.admin.revenue import (
    RevenueOverdueResponse,
    RevenueSummaryResponse,
    RevenueUsageResponse,
)
from app.services.admin_revenue import revenue_overdue_list, revenue_summary, revenue_usage_totals


ALLOWED_ROLES = {"NEFT_SUPERADMIN", "NEFT_FINANCE", "NEFT_SALES"}


def _extract_roles(token: dict) -> set[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = token.get("role")
    if role:
        roles = [*roles, role]
    return {str(value).upper() for value in roles}


def require_revenue_access(token: dict = Depends(require_admin_user)) -> dict:
    roles = _extract_roles(token)
    if not roles.intersection(ALLOWED_ROLES):
        raise HTTPException(status_code=403, detail="forbidden_revenue_role")
    return token


router = APIRouter(prefix="/revenue", tags=["admin", "revenue"])


@router.get("/summary", response_model=RevenueSummaryResponse)
def get_revenue_summary(
    as_of: date | None = Query(None),
    _: dict = Depends(require_revenue_access),
    db: Session = Depends(get_db),
) -> RevenueSummaryResponse:
    target = as_of or date.today()
    return RevenueSummaryResponse(**revenue_summary(db, as_of=target))


@router.get("/overdue", response_model=RevenueOverdueResponse)
def get_overdue_list(
    bucket: str = Query("all", pattern="^(all|0_7|8_30|31_90|90_plus)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    as_of: date | None = Query(None),
    _: dict = Depends(require_revenue_access),
    db: Session = Depends(get_db),
) -> RevenueOverdueResponse:
    target = as_of or date.today()
    items, total = revenue_overdue_list(db, as_of=target, bucket=bucket, limit=limit, offset=offset)
    return RevenueOverdueResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/usage", response_model=RevenueUsageResponse)
def get_usage_totals(
    period_from: date = Query(..., alias="from"),
    period_to: date = Query(..., alias="to"),
    _: dict = Depends(require_revenue_access),
    db: Session = Depends(get_db),
) -> RevenueUsageResponse:
    if period_from > period_to:
        raise HTTPException(status_code=400, detail="invalid_period")
    items = revenue_usage_totals(db, period_from=period_from, period_to=period_to)
    return RevenueUsageResponse(period_from=period_from, period_to=period_to, meters=items)


__all__ = ["router"]
