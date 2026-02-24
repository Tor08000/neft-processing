from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_catalog import MarketplaceProductCardStatus, PartnerVerificationStatus
from app.schemas.marketplace.catalog import (
    PartnerProfileCreate,
    PartnerProfileOut,
)
from app.schemas.marketplace.product_cards import (
    ProductCardCreate,
    ProductCardListOut,
    ProductCardListResponse,
    ProductCardOut,
    ProductCardUpdate,
    ProductMediaCreate,
    ProductMediaOut,
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


def _media_out(media) -> ProductMediaOut:
    return ProductMediaOut(
        attachment_id=str(media.attachment_id),
        bucket=media.bucket,
        path=media.path,
        checksum=media.checksum,
        size=media.size,
        mime=media.mime,
        sort_index=media.sort_index,
        created_at=media.created_at,
    )


def _product_out(product, media_items) -> ProductCardOut:
    return ProductCardOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        title=product.title,
        description=product.description,
        category=product.category,
        status=product.status.value if hasattr(product.status, "value") else product.status,
        tags=product.tags or [],
        attributes=product.attributes or {},
        variants=product.variants or [],
        media=[_media_out(item) for item in media_items],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _product_list_out(product) -> ProductCardListOut:
    return ProductCardListOut(
        id=str(product.id),
        partner_id=str(product.partner_id),
        title=product.title,
        category=product.category,
        status=product.status.value if hasattr(product.status, "value") else product.status,
        updated_at=product.updated_at,
        created_at=product.created_at,
    )


@router.get("/marketplace/profile", response_model=PartnerProfileOut)
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


@router.get("/products", response_model=ProductCardListResponse)
def list_partner_products(
    request: Request,
    status: MarketplaceProductCardStatus | None = Query(None),
    q: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductCardListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    items, total = service.list_partner_product_cards(
        partner_id=partner_id,
        status=status,
        category=category,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return ProductCardListResponse(
        items=[_product_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/products", response_model=ProductCardOut, status_code=status.HTTP_201_CREATED)
def create_partner_product(
    payload: ProductCardCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.create_product_card(partner_id=partner_id, payload=payload.dict())
    db.commit()
    media_items = service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)


@router.get("/products/{product_id}", response_model=ProductCardOut)
def get_partner_product(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    media_items = service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)


@router.patch("/products/{product_id}", response_model=ProductCardOut)
def update_partner_product(
    product_id: str,
    payload: ProductCardUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        product = service.update_product_card(product=product, payload=payload.dict(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    media_items = service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)


@router.post("/products/{product_id}/submit", response_model=ProductCardOut)
def submit_partner_product(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        product = service.submit_product_card(product=product)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    media_items = service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)


@router.post("/products/{product_id}/archive", response_model=ProductCardOut)
def archive_partner_product(
    product_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        product = service.archive_product_card(product=product)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    media_items = service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)


@router.post("/products/{product_id}/media", response_model=ProductMediaOut)
def add_partner_product_media(
    product_id: str,
    payload: ProductMediaCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ProductMediaOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    media = service.upsert_product_media(product_id=product_id, payload=payload.dict())
    db.commit()
    return _media_out(media)


@router.delete("/products/{product_id}/media/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner_product_media(
    product_id: str,
    attachment_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> Response:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    product = service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    if str(product.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    deleted = service.delete_product_media(product_id=product_id, attachment_id=attachment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="media_not_found")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
