from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_catalog import MarketplaceServiceStatus
from app.schemas.marketplace.services import (
    ServiceAvailabilityResponse,
    ServiceCardCreate,
    ServiceCardListOut,
    ServiceCardListResponse,
    ServiceCardOut,
    ServiceCardUpdate,
    ServiceLocationCreate,
    ServiceLocationOut,
    ServiceMediaCreate,
    ServiceMediaOut,
    ServiceScheduleExceptionCreate,
    ServiceScheduleExceptionOut,
    ServiceScheduleOut,
    ServiceScheduleRuleCreate,
    ServiceScheduleRuleOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.marketplace_services_service import MarketplaceServicesService

router = APIRouter(prefix="/partner", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _media_out(media) -> ServiceMediaOut:
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


def _service_out(service, media_items) -> ServiceCardOut:
    return ServiceCardOut(
        id=str(service.id),
        partner_id=str(service.partner_id),
        title=service.title,
        description=service.description,
        category=service.category,
        status=service.status.value if hasattr(service.status, "value") else service.status,
        tags=service.tags or [],
        attributes=service.attributes or {},
        duration_min=service.duration_min,
        requirements=service.requirements,
        media=[_media_out(item) for item in media_items],
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


def _service_list_out(service) -> ServiceCardListOut:
    return ServiceCardListOut(
        id=str(service.id),
        partner_id=str(service.partner_id),
        title=service.title,
        category=service.category,
        status=service.status.value if hasattr(service.status, "value") else service.status,
        duration_min=service.duration_min,
        updated_at=service.updated_at,
        created_at=service.created_at,
    )


def _location_out(location) -> ServiceLocationOut:
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


def _rule_out(rule) -> ServiceScheduleRuleOut:
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


def _exception_out(exception) -> ServiceScheduleExceptionOut:
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


@router.get("/services", response_model=ServiceCardListResponse)
def list_partner_services(
    request: Request,
    status: MarketplaceServiceStatus | None = Query(None),
    q: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceCardListResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    items, total = service.list_partner_services(
        partner_id=partner_id,
        status=status,
        category=category,
        query_text=q,
        limit=limit,
        offset=offset,
    )
    return ServiceCardListResponse(
        items=[_service_list_out(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/services", response_model=ServiceCardOut, status_code=status.HTTP_201_CREATED)
def create_partner_service(
    payload: ServiceCardCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceCardOut:
    partner_id = _ensure_partner_context(principal)
    request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    service = MarketplaceServicesService(db)
    card = service.create_service(partner_id=partner_id, payload=payload.dict())
    db.commit()
    media_items = service.list_service_media(service_id=str(card.id))
    return _service_out(card, media_items)


@router.get("/services/{service_id}", response_model=ServiceCardOut)
def get_partner_service(
    service_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    media_items = service.list_service_media(service_id=str(card.id))
    return _service_out(card, media_items)


@router.patch("/services/{service_id}", response_model=ServiceCardOut)
def update_partner_service(
    service_id: str,
    payload: ServiceCardUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        card = service.update_service(service=card, payload=payload.dict(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    media_items = service.list_service_media(service_id=str(card.id))
    return _service_out(card, media_items)


@router.post("/services/{service_id}/submit", response_model=ServiceCardOut)
def submit_partner_service(
    service_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        card = service.submit_service(service=card)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    media_items = service.list_service_media(service_id=str(card.id))
    return _service_out(card, media_items)


@router.post("/services/{service_id}/archive", response_model=ServiceCardOut)
def archive_partner_service(
    service_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceCardOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        card = service.archive_service(service=card)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    media_items = service.list_service_media(service_id=str(card.id))
    return _service_out(card, media_items)


@router.post("/services/{service_id}/media", response_model=ServiceMediaOut, status_code=status.HTTP_201_CREATED)
def add_partner_service_media(
    service_id: str,
    payload: ServiceMediaCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceMediaOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    media = service.add_service_media(service_id=service_id, payload=payload.dict())
    db.commit()
    return _media_out(media)


@router.delete("/services/{service_id}/media/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_partner_service_media(
    service_id: str,
    attachment_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> Response:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    service.remove_service_media(service_id=service_id, attachment_id=attachment_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/services/{service_id}/locations", response_model=list[ServiceLocationOut])
def list_partner_service_locations(
    service_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> list[ServiceLocationOut]:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    locations = service.list_service_locations(service_id=service_id)
    return [_location_out(item) for item in locations]


@router.post("/services/{service_id}/locations", response_model=ServiceLocationOut, status_code=status.HTTP_201_CREATED)
def add_partner_service_location(
    service_id: str,
    payload: ServiceLocationCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceLocationOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    location = service.add_service_location(service_id=service_id, payload=payload.dict())
    db.commit()
    return _location_out(location)


@router.delete("/services/{service_id}/locations/{service_location_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_partner_service_location(
    service_id: str,
    service_location_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> Response:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    service.remove_service_location(service_id=service_id, service_location_id=service_location_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/service-locations/{service_location_id}/schedule", response_model=ServiceScheduleOut)
def get_partner_service_schedule(
    service_location_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceScheduleOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    location = service.get_service_location(service_location_id=service_location_id)
    if not location:
        raise HTTPException(status_code=404, detail="service_location_not_found")
    card = service.get_service(service_id=str(location.service_id))
    if not card or str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    rules = service.list_schedule_rules(service_location_id=service_location_id)
    exceptions = service.list_schedule_exceptions(service_location_id=service_location_id)
    return ServiceScheduleOut(
        rules=[_rule_out(rule) for rule in rules],
        exceptions=[_exception_out(exc) for exc in exceptions],
    )


@router.post(
    "/service-locations/{service_location_id}/schedule/rules",
    response_model=ServiceScheduleRuleOut,
    status_code=status.HTTP_201_CREATED,
)
def add_partner_service_rule(
    service_location_id: str,
    payload: ServiceScheduleRuleCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceScheduleRuleOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    location = service.get_service_location(service_location_id=service_location_id)
    if not location:
        raise HTTPException(status_code=404, detail="service_location_not_found")
    card = service.get_service(service_id=str(location.service_id))
    if not card or str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        rule = service.add_schedule_rule(
            service_location_id=service_location_id,
            payload=payload.dict(),
            service_duration=card.duration_min,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    return _rule_out(rule)


@router.delete(
    "/service-locations/{service_location_id}/schedule/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_partner_service_rule(
    service_location_id: str,
    rule_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> Response:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    location = service.get_service_location(service_location_id=service_location_id)
    if not location:
        raise HTTPException(status_code=404, detail="service_location_not_found")
    card = service.get_service(service_id=str(location.service_id))
    if not card or str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    service.remove_schedule_rule(service_location_id=service_location_id, rule_id=rule_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/service-locations/{service_location_id}/schedule/exceptions",
    response_model=ServiceScheduleExceptionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_partner_service_exception(
    service_location_id: str,
    payload: ServiceScheduleExceptionCreate,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceScheduleExceptionOut:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    location = service.get_service_location(service_location_id=service_location_id)
    if not location:
        raise HTTPException(status_code=404, detail="service_location_not_found")
    card = service.get_service(service_id=str(location.service_id))
    if not card or str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        exception = service.add_schedule_exception(service_location_id=service_location_id, payload=payload.dict())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    db.commit()
    return _exception_out(exception)


@router.delete(
    "/service-locations/{service_location_id}/schedule/exceptions/{exception_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_partner_service_exception(
    service_location_id: str,
    exception_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> Response:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    location = service.get_service_location(service_location_id=service_location_id)
    if not location:
        raise HTTPException(status_code=404, detail="service_location_not_found")
    card = service.get_service(service_id=str(location.service_id))
    if not card or str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    service.remove_schedule_exception(service_location_id=service_location_id, exception_id=exception_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/services/{service_id}/availability", response_model=ServiceAvailabilityResponse)
def preview_partner_service_availability(
    service_id: str,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    request: Request | None = None,
    principal: Principal = Depends(require_permission("partner:catalog:*")),
    db: Session = Depends(get_db),
) -> ServiceAvailabilityResponse:
    partner_id = _ensure_partner_context(principal)
    service = MarketplaceServicesService(db)
    card = service.get_service(service_id=service_id)
    if not card:
        raise HTTPException(status_code=404, detail="service_not_found")
    if str(card.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")
    date_from = date_from or date.today()
    date_to = date_to or date_from
    locations = service.list_service_locations(service_id=service_id)
    items = service.generate_availability(
        service=card,
        locations=locations,
        date_from=date_from,
        date_to=date_to,
    )
    return ServiceAvailabilityResponse(items=items)
