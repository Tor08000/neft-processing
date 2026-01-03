from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_catalog import (
    MarketplaceProductModerationStatus,
    MarketplaceProductStatus,
    MarketplaceProductType,
    PartnerVerificationStatus,
)
from app.schemas.marketplace.catalog import (
    PartnerProfileCreate,
    PartnerProfileOut,
    ProductCreate,
    ProductListOut,
    ProductListResponse,
    ProductOut,
    ProductUpdate,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_catalog_service import MarketplaceCatalogService

router = APIRouter(prefix="/partner", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


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
        moderation_status=product.moderation_status.value
        if hasattr(product.moderation_status, "value")
        else product.moderation_status,
        moderation_reason=product.moderation_reason,
        moderated_by=str(product.moderated_by) if product.moderated_by else None,
        moderated_at=product.moderated_at,
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
        moderation_status=product.moderation_status.value
        if hasattr(product.moderation_status, "value")
        else product.moderation_status,
        updated_at=product.updated_at,
        published_at=product.published_at,
        created_at=product.created_at,
        sponsored=False,
        sponsored_badge=None,
        sponsored_campaign_id=None,
    )


@router.get("/profile", response_model=PartnerProfileOut)
def get_partner_profile(
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> PartnerProfileOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    profile = service.get_partner_profile(partner_id=partner_id)
    if not profile:
        raise HTTPException(status_code=404, detail="partner_profile_not_found")
    return _profile_out(profile)


@router.post("/profile", response_model=PartnerProfileOut)
def upsert_partner_profile(
    payload: PartnerProfileCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> PartnerProfileOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    profile = service.upsert_partner_profile(
        partner_id=partner_id,
        company_name=payload.company_name,
        description=payload.description,
    )
    db.commit()
    return _profile_out(profile)


@router.get("/products", response_model=ProductListResponse)
def list_partner_products(
    request: Request,
    status: MarketplaceProductStatus | None = Query(None),
    moderation_status: MarketplaceProductModerationStatus | None = Query(None),
    type: MarketplaceProductType | None = Query(None),
    q: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    items, total = service.list_partner_products(
        partner_id=partner_id,
        status=status,
        moderation_status=moderation_status,
        product_type=type,
        category=category,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return ProductListResponse(
        items=[_product_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_partner_product(
    payload: ProductCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.create_product(partner_id=partner_id, payload=payload.dict())
    db.commit()
    return _product_out(product)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_partner_product(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return _product_out(product)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_partner_product(
    product_id: str,
    payload: ProductUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        product = service.update_product(product=product, payload=payload.dict(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _product_out(product)


@router.post("/products/{product_id}/publish", response_model=ProductOut)
def publish_partner_product(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        product = service.publish_product(product=product)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _product_out(product)


@router.post("/products/{product_id}/submit-review", response_model=ProductOut)
def submit_product_review(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        product = service.submit_product_for_review(product=product)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _product_out(product)


@router.post("/products/{product_id}/archive", response_model=ProductOut)
def archive_partner_product(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        product = service.archive_product(product=product)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _product_out(product)


@router.get("/marketplace/products", response_model=ProductListResponse)
def list_partner_marketplace_products(
    request: Request,
    status: MarketplaceProductStatus | None = Query(None),
    moderation_status: MarketplaceProductModerationStatus | None = Query(None),
    type: MarketplaceProductType | None = Query(None),
    q: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    items, total = service.list_partner_products(
        partner_id=partner_id,
        status=status,
        moderation_status=moderation_status,
        product_type=type,
        category=category,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return ProductListResponse(
        items=[_product_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/marketplace/products/{product_id}", response_model=ProductOut)
def get_partner_marketplace_product(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return _product_out(product)


@router.post("/marketplace/products/{product_id}/submit-review", response_model=ProductOut)
def submit_marketplace_product_review(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductOut:
    return submit_product_review(
        product_id=product_id,
        request=request,
        principal=principal,
        db=db,
    )
