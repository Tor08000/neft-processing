from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.models.service_bookings import ServiceBooking, ServiceBookingStatus


router = APIRouter(tags=["service-requests"])


class ServiceRequestCreateIn(BaseModel):
    partner_id: str
    service_id: str
    payload: dict = Field(default_factory=dict)


class ServiceRequestOut(BaseModel):
    id: str
    tenant_id: int
    client_id: str
    partner_id: str
    service_id: str
    status: str
    created_at: datetime | None
    updated_at: datetime | None
    payload: dict


class ServiceRequestActionOut(BaseModel):
    id: str
    status: str


def _map_status(status: str | ServiceBookingStatus) -> str:
    raw = status.value if isinstance(status, ServiceBookingStatus) else str(status)
    mapping = {
        ServiceBookingStatus.REQUESTED.value: "new",
        ServiceBookingStatus.CONFIRMED.value: "accepted",
        ServiceBookingStatus.IN_PROGRESS.value: "in_progress",
        ServiceBookingStatus.COMPLETED.value: "done",
        ServiceBookingStatus.DECLINED.value: "rejected",
        ServiceBookingStatus.CANCELED.value: "rejected",
        ServiceBookingStatus.NO_SHOW.value: "rejected",
    }
    return mapping.get(raw, raw.lower())


def _request_out(item: ServiceBooking) -> ServiceRequestOut:
    return ServiceRequestOut(
        id=str(item.id),
        tenant_id=int(item.tenant_id or 0),
        client_id=str(item.client_id),
        partner_id=str(item.partner_id),
        service_id=str(item.service_id),
        status=_map_status(item.status),
        created_at=item.created_at,
        updated_at=item.updated_at,
        payload={
            "description": item.client_note,
            "partner_note": item.partner_note,
            "price_snapshot": item.price_snapshot_json,
        },
    )


@router.post("/services/requests", response_model=ServiceRequestOut, status_code=201)
def create_service_request(
    payload: ServiceRequestCreateIn,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ServiceRequestOut:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")

    now = datetime.now(timezone.utc)
    booking = ServiceBooking(
        id=str(uuid4()),
        tenant_id=int(token.get("tenant_id") or 0),
        booking_number=f"SR-{uuid4().hex[:10].upper()}",
        client_id=str(client_id),
        user_id=token.get("sub"),
        partner_id=payload.partner_id,
        service_id=payload.service_id,
        status=ServiceBookingStatus.REQUESTED.value,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
        price_snapshot_json={"amount": str(Decimal("0")), "currency": "RUB"},
        payment_status="NONE",
        client_note=str(payload.payload.get("description") or ""),
        partner_note=None,
        promo_applied_json={"payload": payload.payload},
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return _request_out(booking)


@router.get("/services/requests", response_model=list[ServiceRequestOut])
def list_client_service_requests(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> list[ServiceRequestOut]:
    client_id = token.get("client_id")
    items = (
        db.query(ServiceBooking)
        .filter(ServiceBooking.client_id == str(client_id))
        .order_by(ServiceBooking.created_at.desc())
        .all()
    )
    return [_request_out(item) for item in items]


@router.get("/services/requests/{request_id}", response_model=ServiceRequestOut)
def get_client_service_request(
    request_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ServiceRequestOut:
    item = (
        db.query(ServiceBooking)
        .filter(ServiceBooking.id == request_id, ServiceBooking.client_id == str(token.get("client_id")))
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    return _request_out(item)


@router.get("/partner/services/requests", response_model=list[ServiceRequestOut])
def list_partner_service_requests(
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> list[ServiceRequestOut]:
    items = (
        db.query(ServiceBooking)
        .filter(ServiceBooking.partner_id == str(token.get("partner_id")))
        .order_by(ServiceBooking.created_at.desc())
        .all()
    )
    return [_request_out(item) for item in items]


def _change_status(db: Session, *, request_id: str, partner_id: str, to_status: ServiceBookingStatus) -> ServiceBooking:
    item = (
        db.query(ServiceBooking)
        .filter(ServiceBooking.id == request_id, ServiceBooking.partner_id == str(partner_id))
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    item.status = to_status.value
    item.updated_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/partner/services/requests/{request_id}/accept", response_model=ServiceRequestActionOut)
def accept_partner_service_request(request_id: str, token: dict = Depends(partner_portal_user), db: Session = Depends(get_db)) -> ServiceRequestActionOut:
    item = _change_status(db, request_id=request_id, partner_id=str(token.get("partner_id")), to_status=ServiceBookingStatus.CONFIRMED)
    return ServiceRequestActionOut(id=str(item.id), status=_map_status(item.status))


@router.post("/partner/services/requests/{request_id}/reject", response_model=ServiceRequestActionOut)
def reject_partner_service_request(request_id: str, token: dict = Depends(partner_portal_user), db: Session = Depends(get_db)) -> ServiceRequestActionOut:
    item = _change_status(db, request_id=request_id, partner_id=str(token.get("partner_id")), to_status=ServiceBookingStatus.DECLINED)
    return ServiceRequestActionOut(id=str(item.id), status=_map_status(item.status))


@router.post("/partner/services/requests/{request_id}/complete", response_model=ServiceRequestActionOut)
def complete_partner_service_request(request_id: str, token: dict = Depends(partner_portal_user), db: Session = Depends(get_db)) -> ServiceRequestActionOut:
    item = _change_status(db, request_id=request_id, partner_id=str(token.get("partner_id")), to_status=ServiceBookingStatus.COMPLETED)
    return ServiceRequestActionOut(id=str(item.id), status=_map_status(item.status))
