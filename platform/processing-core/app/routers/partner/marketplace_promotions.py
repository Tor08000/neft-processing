from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_promotions import PromotionStatus, PromotionType
from app.schemas.marketplace.promotions import (
    PromotionCreate,
    PromotionListResponse,
    PromotionOut,
    PromotionStatsOut,
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
        tenant_id=int(promotion.tenant_id),
        partner_id=str(promotion.partner_id),
        promo_type=promotion.promo_type.value if hasattr(promotion.promo_type, "value") else promotion.promo_type,
        status=promotion.status.value if hasattr(promotion.status, "value") else promotion.status,
        title=promotion.title,
        description=promotion.description,
        scope=promotion.scope,
        eligibility=promotion.eligibility,
        rules=promotion.rules,
        budget=promotion.budget,
        limits=promotion.limits,
        schedule=promotion.schedule,
        created_at=promotion.created_at,
        updated_at=promotion.updated_at,
        audit_event_id=str(promotion.audit_event_id) if promotion.audit_event_id else None,
    )


def _handle_service_error(exc: MarketplacePromotionServiceError) -> None:
    if exc.code == "promotion_not_found":
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code == "forbidden":
        raise HTTPException(status_code=403, detail="forbidden") from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("", response_model=PromotionListResponse)
def list_partner_promotions(
    request: Request,
    status: PromotionStatus | None = Query(None),
    promo_type: PromotionType | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:marketplace:promotions:*")),
    db: Session = Depends(get_db),
) -> PromotionListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    items, total = service.list_promotions(
        partner_id=partner_id,
        status=status,
        promo_type=promo_type,
        limit=limit,
        offset=offset,
    )
    return PromotionListResponse(items=[_promotion_out(item) for item in items], total=total, limit=limit, offset=offset)


@router.post("", response_model=PromotionOut, status_code=status.HTTP_201_CREATED)
def create_partner_promotion(
    payload: PromotionCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:promotions:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    promotion = service.create_promotion(partner_id=partner_id, payload=payload.dict())
    db.commit()
    return _promotion_out(promotion)


@router.patch("/{promotion_id}", response_model=PromotionOut)
def update_partner_promotion(
    promotion_id: str,
    payload: PromotionUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:promotions:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        promotion = service.update_promotion(partner_id=partner_id, promotion_id=promotion_id, payload=payload.dict())
    except MarketplacePromotionServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _promotion_out(promotion)


@router.post("/{promotion_id}/activate", response_model=PromotionOut)
def activate_partner_promotion(
    promotion_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:promotions:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        promotion = service.set_status(partner_id=partner_id, promotion_id=promotion_id, status=PromotionStatus.ACTIVE)
    except MarketplacePromotionServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _promotion_out(promotion)


@router.post("/{promotion_id}/pause", response_model=PromotionOut)
def pause_partner_promotion(
    promotion_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:promotions:*")),
    db: Session = Depends(get_db),
) -> PromotionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        promotion = service.set_status(partner_id=partner_id, promotion_id=promotion_id, status=PromotionStatus.PAUSED)
    except MarketplacePromotionServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _promotion_out(promotion)


@router.get("/{promotion_id}/stats", response_model=PromotionStatsOut)
def get_promotion_stats(
    promotion_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:marketplace:promotions:*")),
    db: Session = Depends(get_db),
) -> PromotionStatsOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplacePromotionService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        stats = service.promotion_stats(partner_id=partner_id, promotion_id=promotion_id)
    except MarketplacePromotionServiceError as exc:
        _handle_service_error(exc)
    return PromotionStatsOut(**stats)
