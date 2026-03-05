from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.models.service_requests import ServiceRequest, ServiceRequestStatus


router = APIRouter(tags=["service-requests"])


TRANSITIONS: dict[ServiceRequestStatus, set[ServiceRequestStatus]] = {
    ServiceRequestStatus.NEW: {ServiceRequestStatus.ACCEPTED, ServiceRequestStatus.REJECTED},
    ServiceRequestStatus.ACCEPTED: {ServiceRequestStatus.IN_PROGRESS, ServiceRequestStatus.REJECTED},
    ServiceRequestStatus.IN_PROGRESS: {ServiceRequestStatus.DONE, ServiceRequestStatus.REJECTED},
    ServiceRequestStatus.DONE: set(),
    ServiceRequestStatus.REJECTED: set(),
}


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
    created_at: str | None
    updated_at: str | None
    payload: dict


class ServiceRequestActionOut(BaseModel):
    id: str
    status: str


def _tenant_id(token: dict) -> int:
    return int(token.get("tenant_id") or 0)


def _request_out(item: ServiceRequest) -> ServiceRequestOut:
    return ServiceRequestOut(
        id=str(item.id),
        tenant_id=int(item.tenant_id),
        client_id=str(item.client_id),
        partner_id=str(item.partner_id),
        service_id=str(item.service_id),
        status=str(item.status.value if hasattr(item.status, "value") else item.status),
        created_at=item.created_at.isoformat() if item.created_at else None,
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
        payload=item.payload or {},
    )


def _load_for_partner(db: Session, *, request_id: str, token: dict) -> ServiceRequest:
    item = (
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.id == request_id,
            ServiceRequest.partner_id == str(token.get("partner_id")),
            ServiceRequest.tenant_id == _tenant_id(token),
        )
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    return item


def _transition(item: ServiceRequest, target: ServiceRequestStatus) -> None:
    current = ServiceRequestStatus(item.status.value if hasattr(item.status, "value") else str(item.status))
    allowed = TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "invalid_status_transition", "from": current.value, "to": target.value},
        )
    item.status = target.value


@router.post("/services/requests", response_model=ServiceRequestOut, status_code=201)
def create_service_request(
    payload: ServiceRequestCreateIn,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ServiceRequestOut:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")

    item = ServiceRequest(
        tenant_id=_tenant_id(token),
        client_id=str(client_id),
        partner_id=str(payload.partner_id),
        service_id=str(payload.service_id),
        status=ServiceRequestStatus.NEW.value,
        payload=payload.payload,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _request_out(item)


@router.get("/services/requests", response_model=list[ServiceRequestOut])
def list_client_service_requests(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> list[ServiceRequestOut]:
    items = (
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.client_id == str(token.get("client_id")),
            ServiceRequest.tenant_id == _tenant_id(token),
        )
        .order_by(ServiceRequest.created_at.desc())
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
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.id == request_id,
            ServiceRequest.client_id == str(token.get("client_id")),
            ServiceRequest.tenant_id == _tenant_id(token),
        )
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
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.partner_id == str(token.get("partner_id")),
            ServiceRequest.tenant_id == _tenant_id(token),
        )
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )
    return [_request_out(item) for item in items]


@router.post("/partner/services/requests/{request_id}/accept", response_model=ServiceRequestActionOut)
def accept_partner_service_request(
    request_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> ServiceRequestActionOut:
    item = _load_for_partner(db, request_id=request_id, token=token)
    _transition(item, ServiceRequestStatus.ACCEPTED)
    db.add(item)
    db.commit()
    return ServiceRequestActionOut(id=str(item.id), status=str(item.status.value if hasattr(item.status, "value") else item.status))


@router.post("/partner/services/requests/{request_id}/reject", response_model=ServiceRequestActionOut)
def reject_partner_service_request(
    request_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> ServiceRequestActionOut:
    item = _load_for_partner(db, request_id=request_id, token=token)
    _transition(item, ServiceRequestStatus.REJECTED)
    db.add(item)
    db.commit()
    return ServiceRequestActionOut(id=str(item.id), status=str(item.status.value if hasattr(item.status, "value") else item.status))


@router.post("/partner/services/requests/{request_id}/start", response_model=ServiceRequestActionOut)
def start_partner_service_request(
    request_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> ServiceRequestActionOut:
    item = _load_for_partner(db, request_id=request_id, token=token)
    _transition(item, ServiceRequestStatus.IN_PROGRESS)
    db.add(item)
    db.commit()
    return ServiceRequestActionOut(id=str(item.id), status=str(item.status.value if hasattr(item.status, "value") else item.status))


@router.post("/partner/services/requests/{request_id}/complete", response_model=ServiceRequestActionOut)
def complete_partner_service_request(
    request_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> ServiceRequestActionOut:
    item = _load_for_partner(db, request_id=request_id, token=token)
    _transition(item, ServiceRequestStatus.DONE)
    db.add(item)
    db.commit()
    return ServiceRequestActionOut(id=str(item.id), status=str(item.status.value if hasattr(item.status, "value") else item.status))
