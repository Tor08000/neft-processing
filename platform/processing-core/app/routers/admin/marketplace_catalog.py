from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductStatus, PartnerVerificationStatus
from app.schemas.marketplace.catalog import (
    PartnerProfileListResponse,
    PartnerProfileOut,
    PartnerVerifyRequest,
    ProductListOut,
    ProductListResponse,
    ProductOut,
    ProductStatusUpdateRequest,
)
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_catalog_service import MarketplaceCatalogService

router = APIRouter(tags=["admin"])


def _profile_out(profile) -> PartnerProfileOut:
    return PartnerProfileOut(
        id=str(profile.id),
        partner_id=str(profile.partner_id),
        company_name=profile.company_name,
        description=profile.description,
        verification_status=profile.verification_status.value
        if hasattr(profile.verification_status, "value")
        else profile.verification_status,
        rating=profile.rating,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        audit_event_id=str(profile.audit_event_id) if profile.audit_event_id else None,
    )


def _product_out(product) -> ProductOut:
    return ProductOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        type=product.type.value if hasattr(product.type, "value") else product.type,
        title=product.title,
        description=product.description,
        category=product.category,
        price_model=product.price_model.value if hasattr(product.price_model, "value") else product.price_model,
        price_config=product.price_config,
        status=product.status.value if hasattr(product.status, "value") else product.status,
        published_at=product.published_at,
        archived_at=product.archived_at,
        created_at=product.created_at,
        updated_at=product.updated_at,
        audit_event_id=str(product.audit_event_id) if product.audit_event_id else None,
    )


def _product_list_out(product) -> ProductListOut:
    return ProductListOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        type=product.type.value if hasattr(product.type, "value") else product.type,
        title=product.title,
        category=product.category,
        price_model=product.price_model.value if hasattr(product.price_model, "value") else product.price_model,
        price_config=product.price_config,
        status=product.status.value if hasattr(product.status, "value") else product.status,
        updated_at=product.updated_at,
        published_at=product.published_at,
        sponsored=False,
        sponsored_badge=None,
        sponsored_campaign_id=None,
    )


@router.get("/partners", response_model=PartnerProfileListResponse)
def list_partner_profiles(
    request: Request,
    verification_status: PartnerVerificationStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> PartnerProfileListResponse:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    items, total = service.list_partner_profiles(
        verification_status=verification_status,
        limit=limit,
        offset=offset,
    )
    return PartnerProfileListResponse(
        items=[_profile_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/partners/{partner_id}/verify", response_model=PartnerProfileOut)
def verify_partner(
    partner_id: str,
    payload: PartnerVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> PartnerProfileOut:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    try:
        profile = service.verify_partner(
            partner_id=partner_id,
            status=PartnerVerificationStatus(payload.status),
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return _profile_out(profile)


@router.get("/products", response_model=ProductListResponse)
def list_products(
    request: Request,
    status: MarketplaceProductStatus | None = Query(None),
    partner_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductListResponse:
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    items, total = service.list_admin_products(status=status, partner_id=partner_id, limit=limit, offset=offset)
    return ProductListResponse(
        items=[_product_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/products/{product_id}/status", response_model=ProductOut)
def admin_set_product_status(
    product_id: str,
    payload: ProductStatusUpdateRequest,
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
    product = service.admin_set_product_status(
        product=product,
        status=MarketplaceProductStatus(payload.status),
        reason=payload.reason,
    )
    db.commit()
    return _product_out(product)
