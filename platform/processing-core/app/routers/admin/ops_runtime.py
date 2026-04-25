from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin_capability import require_admin_capability
from app.db import get_db
from app.schemas.admin.ops_runtime import (
    OpsBlockedPayoutsResponse,
    OpsFailedExportsResponse,
    OpsFailedImportsResponse,
    OpsHealthResponse,
    OpsSupportBreachesResponse,
    OpsSummaryResponse,
)
from app.services.ops_runtime import (
    build_ops_health,
    build_ops_summary,
    list_blocked_payouts,
    list_failed_exports,
    list_failed_imports,
    list_support_breaches,
)

router = APIRouter(
    prefix="/ops",
    tags=["ops-runtime"],
    dependencies=[Depends(require_admin_capability("ops"))],
)


@router.get("/health", response_model=OpsHealthResponse)
def ops_health(
    _token: dict = Depends(require_admin_capability("ops")),
) -> OpsHealthResponse:
    return build_ops_health()


@router.get("/summary", response_model=OpsSummaryResponse)
def ops_summary(
    db: Session = Depends(get_db),
    _token: dict = Depends(require_admin_capability("ops")),
) -> OpsSummaryResponse:
    return build_ops_summary(db)


@router.get("/payouts/blocked", response_model=OpsBlockedPayoutsResponse)
def ops_blocked_payouts(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_admin_capability("ops")),
) -> OpsBlockedPayoutsResponse:
    items = list_blocked_payouts(db, limit=limit)
    return OpsBlockedPayoutsResponse(items=items)


@router.get("/exports/failed", response_model=OpsFailedExportsResponse)
def ops_failed_exports(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_admin_capability("ops")),
) -> OpsFailedExportsResponse:
    items = list_failed_exports(db, limit=limit)
    return OpsFailedExportsResponse(items=items)


@router.get("/reconciliation/failed", response_model=OpsFailedImportsResponse)
def ops_failed_reconciliation(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_admin_capability("ops")),
) -> OpsFailedImportsResponse:
    items = list_failed_imports(db, limit=limit)
    return OpsFailedImportsResponse(items=items)


@router.get("/support/breaches", response_model=OpsSupportBreachesResponse)
def ops_support_breaches(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _token: dict = Depends(require_admin_capability("ops")),
) -> OpsSupportBreachesResponse:
    items = list_support_breaches(db, limit=limit)
    return OpsSupportBreachesResponse(items=items)


__all__ = ["router"]
