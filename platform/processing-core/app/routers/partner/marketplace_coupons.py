from __future__ import annotations

import csv
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.marketplace.coupons import (
    CouponBatchCreate,
    CouponBatchListResponse,
    CouponBatchOut,
    CouponIssueRequest,
    CouponIssueResponse,
    CouponOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_coupon_service import MarketplaceCouponService, MarketplaceCouponServiceError
from app.models.marketplace_promotions import MarketplaceCoupon

router = APIRouter(prefix="/partner/marketplace/coupons", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _batch_out(batch) -> CouponBatchOut:
    return CouponBatchOut(
        id=str(batch.id),
        tenant_id=str(batch.tenant_id) if batch.tenant_id else None,
        partner_id=str(batch.partner_id),
        promotion_id=str(batch.promotion_id),
        batch_type=batch.batch_type.value if hasattr(batch.batch_type, "value") else batch.batch_type,
        code_prefix=batch.code_prefix,
        total_count=batch.total_count,
        issued_count=batch.issued_count,
        redeemed_count=batch.redeemed_count,
        meta_json=batch.meta_json,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def _coupon_out(coupon) -> CouponOut:
    return CouponOut(
        id=str(coupon.id),
        tenant_id=str(coupon.tenant_id) if coupon.tenant_id else None,
        batch_id=str(coupon.batch_id),
        promotion_id=str(coupon.promotion_id),
        code=coupon.code,
        status=coupon.status.value if hasattr(coupon.status, "value") else coupon.status,
        client_id=str(coupon.client_id) if coupon.client_id else None,
        redeemed_order_id=str(coupon.redeemed_order_id) if coupon.redeemed_order_id else None,
        expires_at=coupon.expires_at,
        issued_at=coupon.issued_at,
        redeemed_at=coupon.redeemed_at,
        created_at=coupon.created_at,
    )


def _handle_service_error(exc: MarketplaceCouponServiceError) -> None:
    if exc.code in {"subscription_forbidden"}:
        raise HTTPException(status_code=403, detail=exc.code) from exc
    if exc.code in {"promotion_not_found", "no_available_coupons"}:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code in {"invalid_batch_type"}:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.post("/batches", response_model=CouponBatchOut, status_code=status.HTTP_201_CREATED)
def create_coupon_batch(
    payload: CouponBatchCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> CouponBatchOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCouponService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        batch = service.create_batch(partner_id=partner_id, payload=payload.dict())
    except MarketplaceCouponServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _batch_out(batch)


@router.get("/batches", response_model=CouponBatchListResponse)
def list_coupon_batches(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> CouponBatchListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCouponService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    result = service.list_batches(partner_id=partner_id, limit=limit, offset=offset)
    return CouponBatchListResponse(
        items=[_batch_out(item) for item in result.items],
        total=result.total,
        limit=limit,
        offset=offset,
    )


@router.get("/batches/{batch_id}", response_model=CouponBatchOut)
def get_coupon_batch(
    batch_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> CouponBatchOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCouponService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    batch = service.get_batch(batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch_not_found")
    if str(batch.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return _batch_out(batch)


@router.post("/batches/{batch_id}/export")
def export_coupon_batch(
    batch_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> Response:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCouponService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    batch = service.get_batch(batch_id=batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch_not_found")
    if str(batch.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    coupons = db.query(MarketplaceCoupon).filter(MarketplaceCoupon.batch_id == batch_id).all()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["code", "status", "client_id", "expires_at"])
    for coupon in coupons:
        writer.writerow(
            [
                coupon.code,
                coupon.status,
                str(coupon.client_id) if coupon.client_id else None,
                coupon.expires_at.isoformat() if coupon.expires_at else None,
            ]
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=coupons-{batch_id}.csv"},
    )


@router.post("/issue", response_model=CouponIssueResponse)
def issue_coupon(
    payload: CouponIssueRequest,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> CouponIssueResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCouponService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    batch = service.get_batch(batch_id=payload.batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch_not_found")
    if str(batch.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        coupon = service.issue_coupon(batch=batch, client_id=payload.client_id)
    except MarketplaceCouponServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return CouponIssueResponse(coupon=_coupon_out(coupon))
