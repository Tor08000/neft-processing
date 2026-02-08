from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.marketplace_moderation import MarketplaceModerationAction, MarketplaceModerationEntityType
from app.schemas.marketplace.moderation import (
    ModerationAuditResponse,
    ModerationEntityType,
    ModerationQueueResponse,
    ModerationRejectRequest,
    ServiceModerationDetail,
)
from app.schemas.marketplace.offers import OfferOut
from app.schemas.marketplace.product_cards import ProductCardOut, ProductMediaOut
from app.schemas.marketplace.services import (
    ServiceLocationOut,
    ServiceMediaOut,
    ServiceScheduleExceptionOut,
    ServiceScheduleOut,
    ServiceScheduleRuleOut,
)
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_catalog_service import MarketplaceCatalogService
from app.services.marketplace_moderation_service import MarketplaceModerationService
from app.services.marketplace_offers_service import MarketplaceOffersService
from app.services.marketplace_services_service import MarketplaceServicesService

router = APIRouter(prefix="/marketplace", tags=["admin"])


def _product_media_out(media) -> ProductMediaOut:
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
        media=[_product_media_out(item) for item in media_items],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _service_media_out(media) -> ServiceMediaOut:
    return ServiceMediaOut(
        attachment_id=str(media.attachment_id),
        bucket=media.bucket,
        path=media.path,
        checksum=media.checksum,
        size=media.size,
        mime=media.mime,
        sort_index=media.sort_index,
        created_at=media.created_at,
    )


def _service_location_out(location) -> ServiceLocationOut:
    return ServiceLocationOut(
        id=str(location.id),
        service_id=str(location.service_id),
        location_id=str(location.location_id),
        address=location.address,
        latitude=float(location.latitude) if location.latitude is not None else None,
        longitude=float(location.longitude) if location.longitude is not None else None,
        is_active=location.is_active,
        created_at=location.created_at,
    )


def _schedule_rule_out(rule) -> ServiceScheduleRuleOut:
    return ServiceScheduleRuleOut(
        id=str(rule.id),
        service_location_id=str(rule.service_location_id),
        weekday=rule.weekday,
        time_from=rule.time_from,
        time_to=rule.time_to,
        slot_duration_min=rule.slot_duration_min,
        capacity=rule.capacity,
        created_at=rule.created_at,
    )


def _schedule_exception_out(exception) -> ServiceScheduleExceptionOut:
    return ServiceScheduleExceptionOut(
        id=str(exception.id),
        service_location_id=str(exception.service_location_id),
        date=exception.date,
        is_closed=exception.is_closed,
        time_from=exception.time_from,
        time_to=exception.time_to,
        capacity_override=exception.capacity_override,
        created_at=exception.created_at,
    )


def _offer_out(offer) -> OfferOut:
    return OfferOut(
        id=str(offer.id),
        partner_id=str(offer.partner_id),
        subject_type=offer.subject_type.value if hasattr(offer.subject_type, "value") else offer.subject_type,
        subject_id=str(offer.subject_id),
        title_override=offer.title_override,
        description_override=offer.description_override,
        status=offer.status.value if hasattr(offer.status, "value") else offer.status,
        moderation_comment=offer.moderation_comment,
        currency=offer.currency,
        price_model=offer.price_model.value if hasattr(offer.price_model, "value") else offer.price_model,
        price_amount=float(offer.price_amount) if offer.price_amount is not None else None,
        price_min=float(offer.price_min) if offer.price_min is not None else None,
        price_max=float(offer.price_max) if offer.price_max is not None else None,
        vat_rate=float(offer.vat_rate) if offer.vat_rate is not None else None,
        terms=offer.terms or {},
        geo_scope=offer.geo_scope.value if hasattr(offer.geo_scope, "value") else offer.geo_scope,
        location_ids=[str(item) for item in (offer.location_ids or [])],
        region_code=offer.region_code,
        entitlement_scope=offer.entitlement_scope.value if hasattr(offer.entitlement_scope, "value") else offer.entitlement_scope,
        allowed_subscription_codes=[str(code) for code in (offer.allowed_subscription_codes or [])],
        allowed_client_ids=[str(client) for client in (offer.allowed_client_ids or [])],
        valid_from=offer.valid_from,
        valid_to=offer.valid_to,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
    )


@router.get("/moderation/queue", response_model=ModerationQueueResponse)
def list_moderation_queue(
    request: Request,
    type: ModerationEntityType | None = Query(None),
    status: str | None = Query("PENDING_REVIEW"),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ModerationQueueResponse:
    service = MarketplaceModerationService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    items, total = service.list_queue(
        entity_type=type,
        status=status,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return ModerationQueueResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/products/{product_id}", response_model=ProductCardOut)
def admin_get_product_card(
    product_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductCardOut:
    service = MarketplaceCatalogService(db)
    product = service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    media_items = service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)


@router.get("/services/{service_id}", response_model=ServiceModerationDetail)
def admin_get_service_card(
    service_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ServiceModerationDetail:
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    media_items = service.list_service_media(service_id=str(card.id))
    locations = service.list_service_locations(service_id=str(card.id))
    rules = []
    exceptions = []
    for location in locations:
        rules.extend(service.list_schedule_rules(service_location_id=str(location.id)))
        exceptions.extend(service.list_schedule_exceptions(service_location_id=str(location.id)))
    schedule = ServiceScheduleOut(
        rules=[_schedule_rule_out(rule) for rule in rules],
        exceptions=[_schedule_exception_out(item) for item in exceptions],
    )
    return ServiceModerationDetail(
        id=str(card.id),
        partner_id=str(card.partner_id),
        title=card.title,
        description=card.description,
        category=card.category,
        status=card.status.value if hasattr(card.status, "value") else card.status,
        tags=card.tags or [],
        attributes=card.attributes or {},
        duration_min=card.duration_min,
        requirements=card.requirements,
        media=[_service_media_out(item) for item in media_items],
        created_at=card.created_at,
        updated_at=card.updated_at,
        locations=[_service_location_out(location) for location in locations],
        schedule=schedule,
    )


@router.get("/offers/{offer_id}", response_model=OfferOut)
def admin_get_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OfferOut:
    service = MarketplaceOffersService(db)
    offer = service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    return _offer_out(offer)


@router.post("/products/{product_id}:approve", response_model=ProductCardOut)
def approve_product_card(
    product_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductCardOut:
    catalog_service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    moderation_service = MarketplaceModerationService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    product = catalog_service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    before_status = product.status.value if hasattr(product.status, "value") else product.status
    try:
        product = catalog_service.approve_product_card(product=product)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    moderation_service.record_audit(
        entity_type=MarketplaceModerationEntityType.PRODUCT,
        entity_id=str(product.id),
        action=MarketplaceModerationAction.APPROVE,
        before_status=before_status,
        after_status=product.status.value if hasattr(product.status, "value") else product.status,
    )
    db.commit()
    media_items = catalog_service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)


@router.post("/products/{product_id}:reject", response_model=ProductCardOut)
def reject_product_card(
    product_id: str,
    payload: ModerationRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ProductCardOut:
    catalog_service = MarketplaceCatalogService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    moderation_service = MarketplaceModerationService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    product = catalog_service.get_product_card(product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    before_status = product.status.value if hasattr(product.status, "value") else product.status
    try:
        product = catalog_service.reject_product_card(product=product, reason=payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    moderation_service.record_audit(
        entity_type=MarketplaceModerationEntityType.PRODUCT,
        entity_id=str(product.id),
        action=MarketplaceModerationAction.REJECT,
        reason_code=payload.reason_code.value,
        comment=payload.comment,
        before_status=before_status,
        after_status=product.status.value if hasattr(product.status, "value") else product.status,
    )
    db.commit()
    media_items = catalog_service.list_product_media(product_id=str(product.id))
    return _product_out(product, media_items)


@router.post("/services/{service_id}:approve", response_model=ServiceModerationDetail)
def approve_service_card(
    service_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ServiceModerationDetail:
    services_service = MarketplaceServicesService(db)
    moderation_service = MarketplaceModerationService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    card = services_service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    before_status = card.status.value if hasattr(card.status, "value") else card.status
    try:
        card = services_service.approve_service(service=card)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    moderation_service.record_audit(
        entity_type=MarketplaceModerationEntityType.SERVICE,
        entity_id=str(card.id),
        action=MarketplaceModerationAction.APPROVE,
        before_status=before_status,
        after_status=card.status.value if hasattr(card.status, "value") else card.status,
    )
    db.commit()
    media_items = services_service.list_service_media(service_id=str(card.id))
    locations = services_service.list_service_locations(service_id=str(card.id))
    rules = []
    exceptions = []
    for location in locations:
        rules.extend(services_service.list_schedule_rules(service_location_id=str(location.id)))
        exceptions.extend(services_service.list_schedule_exceptions(service_location_id=str(location.id)))
    schedule = ServiceScheduleOut(
        rules=[_schedule_rule_out(rule) for rule in rules],
        exceptions=[_schedule_exception_out(item) for item in exceptions],
    )
    return ServiceModerationDetail(
        id=str(card.id),
        partner_id=str(card.partner_id),
        title=card.title,
        description=card.description,
        category=card.category,
        status=card.status.value if hasattr(card.status, "value") else card.status,
        tags=card.tags or [],
        attributes=card.attributes or {},
        duration_min=card.duration_min,
        requirements=card.requirements,
        media=[_service_media_out(item) for item in media_items],
        created_at=card.created_at,
        updated_at=card.updated_at,
        locations=[_service_location_out(location) for location in locations],
        schedule=schedule,
    )


@router.post("/services/{service_id}:reject", response_model=ServiceModerationDetail)
def reject_service_card(
    service_id: str,
    payload: ModerationRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ServiceModerationDetail:
    services_service = MarketplaceServicesService(db)
    moderation_service = MarketplaceModerationService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    card = services_service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    before_status = card.status.value if hasattr(card.status, "value") else card.status
    try:
        card = services_service.reject_service(service=card)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    moderation_service.record_audit(
        entity_type=MarketplaceModerationEntityType.SERVICE,
        entity_id=str(card.id),
        action=MarketplaceModerationAction.REJECT,
        reason_code=payload.reason_code.value,
        comment=payload.comment,
        before_status=before_status,
        after_status=card.status.value if hasattr(card.status, "value") else card.status,
    )
    db.commit()
    media_items = services_service.list_service_media(service_id=str(card.id))
    locations = services_service.list_service_locations(service_id=str(card.id))
    rules = []
    exceptions = []
    for location in locations:
        rules.extend(services_service.list_schedule_rules(service_location_id=str(location.id)))
        exceptions.extend(services_service.list_schedule_exceptions(service_location_id=str(location.id)))
    schedule = ServiceScheduleOut(
        rules=[_schedule_rule_out(rule) for rule in rules],
        exceptions=[_schedule_exception_out(item) for item in exceptions],
    )
    return ServiceModerationDetail(
        id=str(card.id),
        partner_id=str(card.partner_id),
        title=card.title,
        description=card.description,
        category=card.category,
        status=card.status.value if hasattr(card.status, "value") else card.status,
        tags=card.tags or [],
        attributes=card.attributes or {},
        duration_min=card.duration_min,
        requirements=card.requirements,
        media=[_service_media_out(item) for item in media_items],
        created_at=card.created_at,
        updated_at=card.updated_at,
        locations=[_service_location_out(location) for location in locations],
        schedule=schedule,
    )


@router.post("/offers/{offer_id}:approve", response_model=OfferOut)
def approve_offer(
    offer_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OfferOut:
    offers_service = MarketplaceOffersService(db)
    moderation_service = MarketplaceModerationService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    offer = offers_service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    before_status = offer.status.value if hasattr(offer.status, "value") else offer.status
    try:
        offer = offers_service.approve_offer(offer=offer)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    moderation_service.record_audit(
        entity_type=MarketplaceModerationEntityType.OFFER,
        entity_id=str(offer.id),
        action=MarketplaceModerationAction.APPROVE,
        before_status=before_status,
        after_status=offer.status.value if hasattr(offer.status, "value") else offer.status,
    )
    db.commit()
    return _offer_out(offer)


@router.post("/offers/{offer_id}:reject", response_model=OfferOut)
def reject_offer(
    offer_id: str,
    payload: ModerationRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OfferOut:
    offers_service = MarketplaceOffersService(db)
    moderation_service = MarketplaceModerationService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    offer = offers_service.get_offer(offer_id=offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")
    before_status = offer.status.value if hasattr(offer.status, "value") else offer.status
    try:
        offer = offers_service.reject_offer(offer=offer, comment=payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    moderation_service.record_audit(
        entity_type=MarketplaceModerationEntityType.OFFER,
        entity_id=str(offer.id),
        action=MarketplaceModerationAction.REJECT,
        reason_code=payload.reason_code.value,
        comment=payload.comment,
        before_status=before_status,
        after_status=offer.status.value if hasattr(offer.status, "value") else offer.status,
    )
    db.commit()
    return _offer_out(offer)


@router.get("/moderation/audit", response_model=ModerationAuditResponse)
def list_moderation_audit(
    request: Request,
    type: ModerationEntityType = Query(...),
    id: str = Query(...),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> ModerationAuditResponse:
    service = MarketplaceModerationService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token))
    )
    audit_items = service.list_audit(entity_type=MarketplaceModerationEntityType(type.value), entity_id=id)
    items = [
        {
            "id": str(item.id),
            "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None,
            "actor_role": item.actor_role,
            "action": item.action,
            "reason_code": item.reason_code,
            "comment": item.comment,
            "before_status": item.before_status,
            "after_status": item.after_status,
            "created_at": item.created_at,
            "meta": item.meta,
        }
        for item in audit_items
    ]
    return ModerationAuditResponse(items=items)


@router.post("/moderation/offers/{offer_id}:approve", response_model=OfferOut)
def approve_offer_legacy(
    offer_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OfferOut:
    return approve_offer(offer_id=offer_id, request=request, db=db, token=token)


@router.post("/moderation/offers/{offer_id}:reject", response_model=OfferOut)
def reject_offer_legacy(
    offer_id: str,
    payload: ModerationRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> OfferOut:
    return reject_offer(offer_id=offer_id, payload=payload, request=request, db=db, token=token)
