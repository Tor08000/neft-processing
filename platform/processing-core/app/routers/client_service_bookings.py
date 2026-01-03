from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.service_bookings import ServiceBookingStatus
from app.schemas.service_bookings import (
    BookingCancelRequest,
    BookingCreateRequest,
    BookingDetailOut,
    BookingEventOut,
    BookingOut,
    PartnerServiceOut,
    QuoteRequest,
    QuoteResponse,
    SlotListOut,
    SlotLockOut,
    SlotLockRequest,
    SlotOut,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.service_booking_service import ServiceBookingService, ServiceBookingServiceError


router = APIRouter(prefix="/client", tags=["client-portal-v1"])


def _ensure_client_context(principal: Principal) -> str:
    if principal.client_id is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "reason": "missing_ownership_context", "resource": "client"},
        )
    return str(principal.client_id)


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


def _service_out(service) -> PartnerServiceOut:
    return PartnerServiceOut(
        id=str(service.id),
        partner_id=str(service.partner_id),
        title=service.title,
        description=service.description,
        category_code=service.category_code,
        duration_minutes=service.duration_minutes,
        base_price=service.base_price,
        currency=service.currency,
        requires_vehicle=service.requires_vehicle,
        requires_odometer=service.requires_odometer,
        status=service.status.value if hasattr(service.status, "value") else service.status,
        meta=service.meta,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


def _handle_service_error(exc: ServiceBookingServiceError) -> None:
    if exc.code in {"booking_not_found", "service_not_found", "lock_not_found"}:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    if exc.code in {"service_not_active", "invalid_transition", "slot_unavailable", "lock_expired"}:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    if exc.code in {"cancel_not_allowed", "invalid_slot_range"}:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    if exc.code in {"resource_not_found"}:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("/partners/{partner_id}/services", response_model=list[PartnerServiceOut])
def list_partner_services(
    partner_id: str,
    category: str | None = Query(None),
    principal: Principal = Depends(require_permission("client:bookings:create")),
    db: Session = Depends(get_db),
) -> list[PartnerServiceOut]:
    _ensure_client_context(principal)
    service = ServiceBookingService(db)
    items = service.list_partner_services(partner_id=partner_id, category=category)
    return [_service_out(item) for item in items]


@router.get("/bookings/slots", response_model=SlotListOut)
def list_booking_slots(
    partner_id: str = Query(...),
    service_id: str = Query(...),
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    principal: Principal = Depends(require_permission("client:bookings:create")),
    db: Session = Depends(get_db),
) -> SlotListOut:
    _ensure_client_context(principal)
    service = ServiceBookingService(db)
    try:
        timezone_name, slot_step, slots = service.list_slots(
            partner_id=partner_id,
            service_id=service_id,
            date_from=date_from,
            date_to=date_to,
        )
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    return SlotListOut(
        timezone=timezone_name,
        slot_step=slot_step,
        items=[SlotOut(**slot) for slot in slots],
    )


@router.post("/bookings/slot-lock", response_model=SlotLockOut)
def lock_booking_slot(
    payload: SlotLockRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:bookings:create")),
    db: Session = Depends(get_db),
) -> SlotLockOut:
    client_id = _ensure_client_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        lock = service.lock_slot(
            client_id=client_id,
            partner_id=payload.partner_id,
            service_id=payload.service_id,
            resource_id=payload.resource_id,
            starts_at=payload.start,
            ends_at=payload.end,
        )
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return SlotLockOut(lock_id=str(lock.id), expires_at=lock.expires_at)


@router.post("/bookings/quote", response_model=QuoteResponse)
def quote_booking(
    payload: QuoteRequest,
    principal: Principal = Depends(require_permission("client:bookings:create")),
    db: Session = Depends(get_db),
) -> QuoteResponse:
    _ensure_client_context(principal)
    service = ServiceBookingService(db)
    try:
        snapshot = service.quote_price(service_id=payload.service_id, coupon_code=payload.coupon_code)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    return QuoteResponse(price_snapshot=snapshot)


@router.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreateRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:bookings:create")),
    db: Session = Depends(get_db),
) -> BookingOut:
    client_id = _ensure_client_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        booking = service.create_booking(
            client_id=client_id,
            lock_id=payload.lock_id,
            vehicle_id=payload.vehicle_id,
            recommendation_id=payload.recommendation_id,
            client_note=payload.client_note,
        )
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _booking_out(booking)


@router.get("/bookings", response_model=list[BookingOut])
def list_client_bookings(
    status: ServiceBookingStatus | None = Query(None),
    principal: Principal = Depends(require_permission("client:bookings:list")),
    db: Session = Depends(get_db),
) -> list[BookingOut]:
    client_id = _ensure_client_context(principal)
    service = ServiceBookingService(db)
    items = service.list_bookings_for_client(client_id=client_id, status=status)
    return [_booking_out(item) for item in items]


@router.get("/bookings/{booking_id}", response_model=BookingDetailOut)
def get_client_booking(
    booking_id: str,
    principal: Principal = Depends(require_permission("client:bookings:view")),
    db: Session = Depends(get_db),
) -> BookingDetailOut:
    client_id = _ensure_client_context(principal)
    service = ServiceBookingService(db)
    try:
        booking = service.get_booking_for_client(booking_id=booking_id, client_id=client_id)
        events = service.list_booking_events(booking_id=booking_id)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    return BookingDetailOut(**_booking_out(booking).dict(), events=[_event_out(event) for event in events])


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_client_booking(
    booking_id: str,
    payload: BookingCancelRequest,
    request: Request,
    principal: Principal = Depends(require_permission("client:bookings:cancel")),
    db: Session = Depends(get_db),
) -> BookingOut:
    client_id = _ensure_client_context(principal)
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        booking = service.cancel_booking(
            booking_id=booking_id,
            client_id=client_id,
            reason=payload.reason,
        )
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _booking_out(booking)
