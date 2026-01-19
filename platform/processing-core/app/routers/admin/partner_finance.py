from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.partner_finance import PartnerLedgerEntry, PartnerPayoutRequest
from app.schemas.partner_finance import PartnerLedgerEntryOut, PartnerLedgerListResponse, PartnerPayoutRequestOut
from app.services.partner_finance_service import PartnerFinanceService
from app.services.audit_service import request_context_from_request
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal

router = APIRouter(prefix="/partners", tags=["admin-partner-finance"])


def _payout_out(payout: PartnerPayoutRequest) -> PartnerPayoutRequestOut:
    return PartnerPayoutRequestOut(
        id=str(payout.id),
        partner_org_id=str(payout.partner_org_id),
        amount=Decimal(payout.amount),
        currency=payout.currency,
        status=payout.status.value if hasattr(payout.status, "value") else str(payout.status),
        requested_by=str(payout.requested_by) if payout.requested_by else None,
        approved_by=str(payout.approved_by) if payout.approved_by else None,
        created_at=payout.created_at,
        processed_at=payout.processed_at,
    )


@router.get("/ledger", response_model=PartnerLedgerListResponse)
def admin_partner_ledger(
    partner_org_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("admin:settlement:*")),
    db: Session = Depends(get_db),
) -> PartnerLedgerListResponse:
    query = db.query(PartnerLedgerEntry)
    if partner_org_id:
        query = query.filter(PartnerLedgerEntry.partner_org_id == partner_org_id)
    entries = (
        query.order_by(PartnerLedgerEntry.created_at.desc())
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


def _get_payout(db: Session, payout_id: str) -> PartnerPayoutRequest:
    payout = db.query(PartnerPayoutRequest).filter(PartnerPayoutRequest.id == payout_id).one_or_none()
    if not payout:
        raise HTTPException(status_code=404, detail="payout_request_not_found")
    return payout


@router.post("/payouts/{payout_id}/approve", response_model=PartnerPayoutRequestOut)
def approve_payout(
    payout_id: str,
    principal: Principal = Depends(require_permission("admin:settlement:*")),
    db: Session = Depends(get_db),
) -> PartnerPayoutRequestOut:
    payout = _get_payout(db, payout_id)
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(None, token=principal.raw_claims))
    try:
        service.approve_payout(payout=payout, approved_by=str(principal.user_id) if principal.user_id else None)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _payout_out(payout)


@router.post("/payouts/{payout_id}/reject", response_model=PartnerPayoutRequestOut)
def reject_payout(
    payout_id: str,
    principal: Principal = Depends(require_permission("admin:settlement:*")),
    db: Session = Depends(get_db),
) -> PartnerPayoutRequestOut:
    payout = _get_payout(db, payout_id)
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(None, token=principal.raw_claims))
    try:
        service.reject_payout(payout=payout, approved_by=str(principal.user_id) if principal.user_id else None)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _payout_out(payout)


@router.post("/payouts/{payout_id}/mark-paid", response_model=PartnerPayoutRequestOut)
def mark_payout_paid(
    payout_id: str,
    principal: Principal = Depends(require_permission("admin:settlement:*")),
    db: Session = Depends(get_db),
) -> PartnerPayoutRequestOut:
    payout = _get_payout(db, payout_id)
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(None, token=principal.raw_claims))
    try:
        service.mark_paid(payout=payout)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _payout_out(payout)
