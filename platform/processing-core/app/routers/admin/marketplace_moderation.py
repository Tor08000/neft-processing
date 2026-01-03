from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductModerationStatus
from app.schemas.marketplace.catalog import ProductListResponse, ProductOut, ProductModerationRejectRequest
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_catalog_service import MarketplaceCatalogService
from app.routers.admin.marketplace_catalog import _product_list_out, _product_out

router = APIRouter(prefix="/marketplace/moderation", tags=["admin"])


@router.get("/queue", response_model=ProductListResponse)
def list_moderation_queue(
    request: Request,
    status: MarketplaceProductModerationStatus | None = Query(MarketplaceProductModerationStatus.PENDING_REVIEW),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductListResponse:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    items, total = service.list_moderation_queue(status=status, limit=limit, offset=offset)
    return ProductListResponse(
        items=[_product_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{product_id}/approve", response_model=ProductOut)
def approve_product(
    product_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductOut:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    try:
        product = service.approve_product(product=product)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _product_out(product)


@router.post("/{product_id}/reject", response_model=ProductOut)
def reject_product(
    product_id: str,
    payload: ProductModerationRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductOut:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    try:
        product = service.reject_product(product=product, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _product_out(product)
