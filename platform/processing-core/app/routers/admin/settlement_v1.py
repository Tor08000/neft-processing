from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.settlement_v1 import SettlementItem, SettlementPeriod, SettlementPayout, SettlementPeriodStatus
from app.schemas.admin.settlement import (
    PayoutListResponse,
    PayoutOut,
    SettlementItemOut,
    SettlementPeriodCalculateRequest,
    SettlementPeriodListResponse,
    SettlementPeriodOut,
    SettlementPeriodPayoutRequest,
)
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.settlement_service import (
    SettlementServiceError,
    approve_settlement,
    calculate_settlement_period,
    execute_payout,
)
from app.api.dependencies.admin import require_admin_user


router = APIRouter(prefix="/settlement", tags=["admin", "settlement"])


def _period_out(period: SettlementPeriod, *, items: list[SettlementItem] | None = None) -> SettlementPeriodOut:
    payload = SettlementPeriodOut.model_validate(period)
    if items is not None:
        payload.items = [SettlementItemOut.model_validate(item) for item in items]
    return payload


@router.post("/periods/calculate", response_model=SettlementPeriodOut)
def calculate_period(
    body: SettlementPeriodCalculateRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> SettlementPeriodOut:
    ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        period = calculate_settlement_period(
            db,
            partner_id=body.partner_id,
            currency=body.currency,
            period_start=body.period_start,
            period_end=body.period_end,
            actor=ctx,
            idempotency_key=body.idempotency_key,
        )
        db.commit()
    except SettlementServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _period_out(period)


@router.post("/periods/{period_id}/approve", response_model=SettlementPeriodOut)
def approve_period(
    period_id: str,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> SettlementPeriodOut:
    ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        period = approve_settlement(db, period_id=period_id, actor=ctx)
        db.commit()
    except SettlementServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _period_out(period)


@router.post("/periods/{period_id}/payout", response_model=PayoutOut)
def payout_period(
    period_id: str,
    body: SettlementPeriodPayoutRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> PayoutOut:
    ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    try:
        payout = execute_payout(
            db,
            period_id=period_id,
            provider=body.provider,
            idempotency_key=body.idempotency_key,
            actor=ctx,
        )
        db.commit()
    except SettlementServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PayoutOut.model_validate(payout)


@router.get("/periods", response_model=SettlementPeriodListResponse)
def list_periods(
    partner_id: str | None = Query(None),
    status: SettlementPeriodStatus | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
) -> SettlementPeriodListResponse:
    query = db.query(SettlementPeriod)
    if partner_id:
        query = query.filter(SettlementPeriod.partner_id == partner_id)
    if status:
        query = query.filter(SettlementPeriod.status == status)
    if from_dt:
        query = query.filter(SettlementPeriod.period_start >= from_dt)
    if to_dt:
        query = query.filter(SettlementPeriod.period_end <= to_dt)
    items = query.order_by(SettlementPeriod.period_start.desc()).all()
    return SettlementPeriodListResponse(items=[_period_out(item) for item in items], total=len(items))


@router.get("/periods/{period_id}", response_model=SettlementPeriodOut)
def get_period(period_id: str, db: Session = Depends(get_db)) -> SettlementPeriodOut:
    period = db.query(SettlementPeriod).filter(SettlementPeriod.id == period_id).one_or_none()
    if period is None:
        raise HTTPException(status_code=404, detail="settlement_period_not_found")
    items = db.query(SettlementItem).filter(SettlementItem.settlement_period_id == period.id).all()
    return _period_out(period, items=items)


@router.get("/payouts", response_model=PayoutListResponse)
def list_payouts(
    partner_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> PayoutListResponse:
    query = db.query(SettlementPayout)
    if partner_id:
        query = query.filter(SettlementPayout.partner_id == partner_id)
    items = query.order_by(SettlementPayout.created_at.desc()).all()
    return PayoutListResponse(items=[PayoutOut.model_validate(item) for item in items], total=len(items))


@router.get("/payouts/{payout_id}", response_model=PayoutOut)
def get_payout(payout_id: str, db: Session = Depends(get_db)) -> PayoutOut:
    payout = db.query(SettlementPayout).filter(SettlementPayout.id == payout_id).one_or_none()
    if payout is None:
        raise HTTPException(status_code=404, detail="payout_not_found")
    return PayoutOut.model_validate(payout)
