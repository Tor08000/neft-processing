from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.service_bookings import ServiceBookingStatus
from app.schemas.service_bookings import (
    AvailabilityRuleIn,
    AvailabilityRuleOut,
    BookingDetailOut,
    BookingEventOut,
    BookingOut,
    PartnerCalendarIn,
    PartnerCalendarOut,
    PartnerResourceIn,
    PartnerResourceOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.service_booking_service import ServiceBookingService, ServiceBookingServiceError


router = APIRouter(prefix="/partner/bookings", tags=["partner-portal-v1"])


def _ensure_partner_context(principal: Principal) -> str:
    if principal.partner_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "partner"},
        )
    return str(principal.partner_id)


def _booking_out(booking) -> BookingOut:
    return BookingOut(
        id=str(booking.id),
        booking_number=booking.booking_number,
        client_id=str(booking.client_id),
        partner_id=str(booking.partner_id),
        service_id=str(booking.service_id),
        vehicle_id=str(booking.vehicle_id) if booking.vehicle_id else None,
        odometer_km=booking.odometer_km,
        recommendation_id=str(booking.recommendation_id) if booking.recommendation_id else None,
        status=booking.status.value if hasattr(booking.status, "value") else booking.status,
        starts_at=booking.starts_at,
        ends_at=booking.ends_at,
        resource_id=str(booking.resource_id) if booking.resource_id else None,
        price_snapshot_json=booking.price_snapshot_json,
        promo_applied_json=booking.promo_applied_json,
        payment_status=booking.payment_status.value if hasattr(booking.payment_status, "value") else booking.payment_status,
        client_note=booking.client_note,
        partner_note=booking.partner_note,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )


def _event_out(event) -> BookingEventOut:
    return BookingEventOut(
        id=str(event.id),
        booking_id=str(event.booking_id),
        event_type=event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
        actor_type=event.actor_type.value if hasattr(event.actor_type, "value") else event.actor_type,
        actor_id=str(event.actor_id) if event.actor_id else None,
        payload=event.payload,
        audit_event_id=str(event.audit_event_id),
        created_at=event.created_at,
    )


def _calendar_out(calendar) -> PartnerCalendarOut:
    return PartnerCalendarOut(
        id=str(calendar.id),
        partner_id=str(calendar.partner_id),
        location_id=str(calendar.location_id) if calendar.location_id else None,
        timezone=calendar.timezone,
        working_hours=calendar.working_hours,
        holidays=calendar.holidays,
        slot_step_minutes=calendar.slot_step_minutes,
        created_at=calendar.created_at,
        updated_at=calendar.updated_at,
    )


def _resource_out(resource) -> PartnerResourceOut:
    return PartnerResourceOut(
        id=str(resource.id),
        partner_id=str(resource.partner_id),
        title=resource.title,
        resource_type=resource.resource_type.value if hasattr(resource.resource_type, "value") else resource.resource_type,
        capacity=resource.capacity,
        status=resource.status.value if hasattr(resource.status, "value") else resource.status,
        meta=resource.meta,
    )


def _rule_out(rule) -> AvailabilityRuleOut:
    return AvailabilityRuleOut(
        id=str(rule.id),
        partner_id=str(rule.partner_id),
        service_id=str(rule.service_id),
        resource_ids=[str(resource_id) for resource_id in (rule.resource_ids or [])],
        lead_time_minutes=rule.lead_time_minutes,
        max_days_ahead=rule.max_days_ahead,
        parallel_capacity=rule.parallel_capacity,
        meta=rule.meta,
    )


def _handle_service_error(exc: ServiceBookingServiceError) -> None:
    if exc.code in {"booking_not_found", "resource_not_found"}:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code == "invalid_transition":
        raise HTTPException(status_code=409, detail=exc.code) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("", response_model=list[BookingOut])
def list_partner_bookings(
    status: ServiceBookingStatus | None = None,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> list[BookingOut]:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(db)
    items = service.list_bookings_for_partner(partner_id=partner_id, status=status)
    return [_booking_out(item) for item in items]


@router.get("/{booking_id}", response_model=BookingDetailOut)
def get_partner_booking(
    booking_id: str,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> BookingDetailOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(db)
    try:
        booking = service.get_booking_for_partner(booking_id=booking_id, partner_id=partner_id)
        events = service.list_booking_events(booking_id=booking_id)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    return BookingDetailOut(**_booking_out(booking).dict(), events=[_event_out(event) for event in events])


@router.post("/{booking_id}/confirm", response_model=BookingOut)
def confirm_booking(
    booking_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> BookingOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        booking = service.confirm_booking(booking_id=booking_id, partner_id=partner_id)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _booking_out(booking)


@router.post("/{booking_id}/decline", response_model=BookingOut)
def decline_booking(
    booking_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> BookingOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        booking = service.decline_booking(booking_id=booking_id, partner_id=partner_id, reason=None)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _booking_out(booking)


@router.post("/{booking_id}/start", response_model=BookingOut)
def start_booking(
    booking_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> BookingOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        booking = service.start_booking(booking_id=booking_id, partner_id=partner_id)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _booking_out(booking)


@router.post("/{booking_id}/complete", response_model=BookingOut)
def complete_booking(
    booking_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> BookingOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        booking = service.complete_booking(booking_id=booking_id, partner_id=partner_id)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _booking_out(booking)


@router.post("/{booking_id}/no-show", response_model=BookingOut)
def mark_booking_no_show(
    booking_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> BookingOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        booking = service.mark_no_show(booking_id=booking_id, partner_id=partner_id)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _booking_out(booking)


@router.get("/calendar", response_model=PartnerCalendarOut | None)
def get_partner_calendar(
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> PartnerCalendarOut | None:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(db)
    calendar = service._get_calendar(partner_id=partner_id)
    return _calendar_out(calendar) if calendar else None


@router.patch("/calendar", response_model=PartnerCalendarOut)
def update_partner_calendar(
    payload: PartnerCalendarIn,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> PartnerCalendarOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    calendar = service.update_partner_calendar(
        partner_id=partner_id,
        timezone_name=payload.timezone,
        working_hours=payload.working_hours,
        holidays=payload.holidays,
        slot_step_minutes=payload.slot_step_minutes,
    )
    db.commit()
    return _calendar_out(calendar)


@router.get("/resources", response_model=list[PartnerResourceOut])
def list_partner_resources(
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> list[PartnerResourceOut]:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(db)
    resources = service.list_resources(partner_id=partner_id)
    return [_resource_out(resource) for resource in resources]


@router.post("/resources", response_model=PartnerResourceOut, status_code=status.HTTP_201_CREATED)
def create_partner_resource(
    payload: PartnerResourceIn,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> PartnerResourceOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    resource = service.create_resource(partner_id=partner_id, payload=payload.dict())
    db.commit()
    return _resource_out(resource)


@router.put("/resources/{resource_id}", response_model=PartnerResourceOut)
def update_partner_resource(
    resource_id: str,
    payload: PartnerResourceIn,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> PartnerResourceOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        resource = service.update_resource(partner_id=partner_id, resource_id=resource_id, payload=payload.dict())
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _resource_out(resource)


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner_resource(
    resource_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> None:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        service.delete_resource(partner_id=partner_id, resource_id=resource_id)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return None


@router.put("/services/{service_id}/availability", response_model=AvailabilityRuleOut)
def upsert_service_availability(
    service_id: str,
    payload: AvailabilityRuleIn,
    request: Request,
    principal: Principal = Depends(require_permission("partner:bookings:*")),
    db: Session = Depends(get_db),
) -> AvailabilityRuleOut:
    partner_id = _ensure_partner_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    rule = service.upsert_availability_rule(
        partner_id=partner_id,
        payload={**payload.dict(), "service_id": service_id},
    )
    db.commit()
    return _rule_out(rule)
