from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.partner_finance import PartnerLedgerEntry
from app.models.settlement_v1 import SettlementPeriod
from app.routers.admin.finance import get_payout_detail as finance_get_payout_detail
from app.routers.admin.finance import list_payout_queue as finance_list_payout_queue
from app.schemas.admin.finance import (
    PartnerSettlementBreakdown,
    PartnerSettlementSnapshotResponse,
    PayoutDetail,
    PayoutQueueListResponse,
)
from app.schemas.partner_finance import PartnerLedgerEntryOut, PartnerLedgerListResponse

# Hidden compatibility bridge for `/api/core/admin/*` finance aliases.
# Canonical owner routes live under `/api/core/v1/admin/finance/*`.
router = APIRouter(prefix="/admin", tags=["admin-core-finance"], dependencies=[Depends(require_admin_user)])


@router.get("/payouts", response_model=PayoutQueueListResponse)
def list_admin_payouts(
    status: str | None = Query(None),
    blocked: bool | None = Query(None),
    reason: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PayoutQueueListResponse:
    return finance_list_payout_queue(
        status=status,
        blocked=blocked,
        reason=reason,
        limit=limit,
        offset=offset,
        db=db,
    )


@router.get("/payouts/{payout_id}", response_model=PayoutDetail)
def get_admin_payout(payout_id: str, db: Session = Depends(get_db)) -> PayoutDetail:
    return finance_get_payout_detail(payout_id=payout_id, db=db)


@router.get("/partner/{partner_id}/ledger", response_model=PartnerLedgerListResponse)
def get_partner_ledger(
    partner_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PartnerLedgerListResponse:
    entries = (
        db.query(PartnerLedgerEntry)
        .filter(PartnerLedgerEntry.partner_org_id == partner_id)
        .order_by(PartnerLedgerEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PartnerLedgerListResponse(
        items=[
            PartnerLedgerEntryOut(
                id=str(entry.id),
                partner_org_id=str(entry.partner_org_id),
                order_id=str(entry.order_id) if entry.order_id else None,
                entry_type=entry.entry_type.value if hasattr(entry.entry_type, "value") else str(entry.entry_type),
                amount=Decimal(entry.amount),
                currency=entry.currency,
                direction=entry.direction.value if hasattr(entry.direction, "value") else str(entry.direction),
                meta_json=entry.meta_json,
                created_at=entry.created_at,
            )
            for entry in entries
        ]
    )


@router.get("/partner/{partner_id}/settlement", response_model=PartnerSettlementSnapshotResponse)
def get_partner_settlement_snapshot(
    partner_id: str,
    currency: str | None = Query(None),
    db: Session = Depends(get_db),
) -> PartnerSettlementSnapshotResponse:
    query = db.query(SettlementPeriod).filter(SettlementPeriod.partner_id == partner_id)
    if currency:
        query = query.filter(SettlementPeriod.currency == currency)
    period = query.order_by(SettlementPeriod.period_end.desc()).first()
    if not period:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    breakdown = PartnerSettlementBreakdown(
        gross=Decimal(period.total_gross or 0),
        fee=Decimal(period.total_fees or 0),
        penalty=Decimal(period.total_refunds or 0),
        net=Decimal(period.net_amount or 0),
    )
    status = period.status.value if hasattr(period.status, "value") else str(period.status)
    return PartnerSettlementSnapshotResponse(
        partner_org_id=str(period.partner_id),
        settlement_id=str(period.id),
        currency=period.currency,
        status=status,
        period_start=period.period_start,
        period_end=period.period_end,
        breakdown=breakdown,
    )


__all__ = ["router"]
