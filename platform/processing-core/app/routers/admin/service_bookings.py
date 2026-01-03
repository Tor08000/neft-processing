from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.service_bookings import BookingCancelRequest, BookingDetailOut, BookingEventOut, BookingOut
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request
from app.services.service_booking_service import ServiceBookingService, ServiceBookingServiceError


router = APIRouter(prefix="/bookings", tags=["admin"])


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


def _handle_service_error(exc: ServiceBookingServiceError) -> None:
    if exc.code == "booking_not_found":
        raise HTTPException(status_code=404, detail=exc.code) from exc
    raise HTTPException(status_code=400, detail=exc.code) from exc


@router.get("/{booking_id}", response_model=BookingDetailOut)
def get_admin_booking(
    booking_id: str,
    principal: Principal = Depends(require_permission("admin:bookings:*")),
    db: Session = Depends(get_db),
) -> BookingDetailOut:
    service = ServiceBookingService(db)
    try:
        booking = service.get_booking_admin(booking_id=booking_id)
        events = service.list_booking_events(booking_id=booking_id)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    return BookingDetailOut(**_booking_out(booking).dict(), events=[_event_out(event) for event in events])


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_admin_booking(
    booking_id: str,
    payload: BookingCancelRequest,
    request: Request,
    principal: Principal = Depends(require_permission("admin:bookings:*")),
    db: Session = Depends(get_db),
) -> BookingOut:
    service = ServiceBookingService(
        db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims))
    )
    try:
        booking = service.cancel_booking_admin(booking_id=booking_id, reason=payload.reason)
    except ServiceBookingServiceError as exc:
        _handle_service_error(exc)
    db.commit()
    return _booking_out(booking)
