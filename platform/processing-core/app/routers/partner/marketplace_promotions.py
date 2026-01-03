from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_promotions import MarketplacePromotionStatus
from app.schemas.marketplace.promotions import (
    PromotionCreate,
    PromotionListResponse,
    PromotionOut,
    PromotionUpdate,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_promotion_service import (
    MarketplacePromotionService,
    MarketplacePromotionServiceError,
)

router = APIRouter(prefix="/partner/marketplace/promotions", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _promotion_out(promotion) -> PromotionOut:
    return PromotionOut(
        id=str(promotion.id),
        tenant_id=str(promotion.tenant_id) if promotion.tenant_id else None,
        partner_id=str(promotion.partner_id),
        promo_type=promotion.promo_type.value if hasattr(promotion.promo_type, "value") else promotion.promo_type,
        status=promotion.status.value if hasattr(promotion.status, "value") else promotion.status,
        title=promotion.title,
        description=promotion.description,
        scope_json=promotion.scope_json,
        eligibility_json=promotion.eligibility_json,
        rules_json=promotion.rules_json,
        schedule_json=promotion.schedule_json,
        limits_json=promotion.limits_json,
        created_at=promotion.created_at,
        updated_at=promotion.updated_at,
        created_by=str(promotion.created_by) if promotion.created_by else None,
        updated_by=str(promotion.updated_by) if promotion.updated_by else None,
    )


def _handle_service_error(exc: MarketplacePromotionServiceError) -> None:
    if exc.code in {"subscription_forbidden", "promotion_locked"}:
        raise HTTPException(status_code=403, detail=exc.code) from exc
    if exc.code in {"invalid_scope", "invalid_discount_type", "invalid_discount_value", "invalid_stacking_rule"}:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    if exc.code in {"free_plan_active_limit_reached"}:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.post("", response_model=PromotionOut, status_code=status.HTTP_201_CREATED)
def create_promotion(
    payload: PromotionCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        promotion = service.create_promotion(partner_id=partner_id, payload=payload.dict(by_alias=True))
    except MarketplacePromotionServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _promotion_out(promotion)


@router.get("", response_model=PromotionListResponse)
def list_promotions(
    request: Request,
    status: MarketplacePromotionStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PromotionListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    result = service.list_promotions(partner_id=partner_id, status=status, limit=limit, offset=offset)
    return PromotionListResponse(
        items=[_promotion_out(item) for item in result.items],
        total=result.total,
        limit=limit,
        offset=offset,
    )


@router.get("/{promotion_id}", response_model=PromotionOut)
def get_promotion(
    promotion_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    promotion = service.get_promotion(promotion_id=promotion_id)
    if not promotion:
        raise HTTPException(status_code=404, detail="promotion_not_found")
    if str(promotion.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return _promotion_out(promotion)


@router.patch("/{promotion_id}", response_model=PromotionOut)
def update_promotion(
    promotion_id: str,
    payload: PromotionUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    promotion = service.get_promotion(promotion_id=promotion_id)
    if not promotion:
        raise HTTPException(status_code=404, detail="promotion_not_found")
    if str(promotion.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        promotion = service.update_promotion(promotion=promotion, payload=payload.dict(by_alias=True, exclude_unset=True))
    except MarketplacePromotionServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _promotion_out(promotion)


def _set_status(
    *,
    promotion_id: str,
    status: MarketplacePromotionStatus,
    request: Request,
    principal: Principal,
    db: Session,
) -> PromotionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    promotion = service.get_promotion(promotion_id=promotion_id)
    if not promotion:
        raise HTTPException(status_code=404, detail="promotion_not_found")
    if str(promotion.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        promotion = service.set_status(promotion=promotion, status=status)
    except MarketplacePromotionServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _promotion_out(promotion)


@router.post("/{promotion_id}/activate", response_model=PromotionOut)
def activate_promotion(
    promotion_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    return _set_status(
        promotion_id=promotion_id,
        status=MarketplacePromotionStatus.ACTIVE,
        request=request,
        principal=principal,
        db=db,
    )


@router.post("/{promotion_id}/pause", response_model=PromotionOut)
def pause_promotion(
    promotion_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    return _set_status(
        promotion_id=promotion_id,
        status=MarketplacePromotionStatus.PAUSED,
        request=request,
        principal=principal,
        db=db,
    )


@router.post("/{promotion_id}/end", response_model=PromotionOut)
def end_promotion(
    promotion_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    return _set_status(
        promotion_id=promotion_id,
        status=MarketplacePromotionStatus.ENDED,
        request=request,
        principal=principal,
        db=db,
    )


@router.post("/{promotion_id}/archive", response_model=PromotionOut)
def archive_promotion(
    promotion_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:orders:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    return _set_status(
        promotion_id=promotion_id,
        status=MarketplacePromotionStatus.ARCHIVED,
        request=request,
        principal=principal,
        db=db,
    )
