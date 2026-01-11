from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.service_identities import ServiceIdentity, ServiceToken
from app.schemas.admin.security import (
    ServiceIdentityCreateIn,
    ServiceIdentityOut,
    ServiceTokenIssueIn,
    ServiceTokenIssueOut,
    ServiceTokenOut,
    ServiceTokenRevokeIn,
    ServiceTokenRotateIn,
)
from app.services.service_identities import issue_service_token, rotate_service_token, revoke_service_token


router = APIRouter(prefix="/security", tags=["security"])


def _serialize_identity(record: ServiceIdentity) -> ServiceIdentityOut:
    return ServiceIdentityOut(
        id=str(record.id),
        service_name=record.service_name,
        description=record.description,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _serialize_token(record: ServiceToken) -> ServiceTokenOut:
    return ServiceTokenOut(
        id=str(record.id),
        service_identity_id=str(record.service_identity_id),
        prefix=record.prefix,
        scopes=list(record.scopes or []),
        issued_at=record.issued_at,
        expires_at=record.expires_at,
        rotated_from_id=str(record.rotated_from_id) if record.rotated_from_id else None,
        rotation_grace_until=record.rotation_grace_until,
        last_used_at=record.last_used_at,
        status=record.status,
    )


@router.post("/service-identities", response_model=ServiceIdentityOut)
def create_service_identity(
    payload: ServiceIdentityCreateIn,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ServiceIdentityOut:
    existing = db.query(ServiceIdentity).filter(ServiceIdentity.service_name == payload.service_name).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="service_identity_exists")
    record = ServiceIdentity(
        service_name=payload.service_name,
        description=payload.description,
        status=payload.status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _serialize_identity(record)


@router.get("/service-identities", response_model=list[ServiceIdentityOut])
def list_service_identities(
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> list[ServiceIdentityOut]:
    identities = db.query(ServiceIdentity).order_by(ServiceIdentity.created_at.desc()).all()
    return [_serialize_identity(record) for record in identities]


@router.post("/service-identities/{identity_id}/tokens/issue", response_model=ServiceTokenIssueOut)
def issue_service_token_endpoint(
    identity_id: str,
    payload: ServiceTokenIssueIn,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ServiceTokenIssueOut:
    identity = db.query(ServiceIdentity).filter(ServiceIdentity.id == identity_id).one_or_none()
    if not identity:
        raise HTTPException(status_code=404, detail="service_identity_not_found")
    if payload.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="expires_at_in_past")
    record, plaintext = issue_service_token(
        db,
        service_identity=identity,
        scopes=payload.scopes,
        expires_at=payload.expires_at,
        actor_id=token.get("user_id") or token.get("sub"),
        request=request,
        env=payload.env,
    )
    db.commit()
    return ServiceTokenIssueOut(
        token=plaintext,
        token_id=str(record.id),
        prefix=record.prefix,
        scopes=list(record.scopes),
        expires_at=record.expires_at,
    )


@router.post("/service-tokens/{token_id}/rotate", response_model=ServiceTokenIssueOut)
def rotate_service_token_endpoint(
    token_id: str,
    payload: ServiceTokenRotateIn,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ServiceTokenIssueOut:
    record = db.query(ServiceToken).filter(ServiceToken.id == token_id).one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="service_token_not_found")
    new_record, plaintext = rotate_service_token(
        db,
        token=record,
        actor_id=token.get("user_id") or token.get("sub"),
        request=request,
        grace_hours=payload.grace_hours,
        env=payload.env,
        expires_at=payload.expires_at,
    )
    db.commit()
    return ServiceTokenIssueOut(
        token=plaintext,
        token_id=str(new_record.id),
        prefix=new_record.prefix,
        scopes=list(new_record.scopes),
        expires_at=new_record.expires_at,
    )


@router.post("/service-tokens/{token_id}/revoke", response_model=ServiceTokenOut)
def revoke_service_token_endpoint(
    token_id: str,
    payload: ServiceTokenRevokeIn,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ServiceTokenOut:
    record = db.query(ServiceToken).filter(ServiceToken.id == token_id).one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="service_token_not_found")
    revoke_service_token(
        db,
        token=record,
        actor_id=token.get("user_id") or token.get("sub"),
        request=request,
        reason=payload.reason,
    )
    db.commit()
    db.refresh(record)
    return _serialize_token(record)


__all__ = ["router"]
