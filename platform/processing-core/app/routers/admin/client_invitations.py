from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.client_invitations import ClientInvitation
from app.schemas.client_portal_v1 import ClientInvitationActionResponse, ClientInvitationsResponse, ClientInvitationSummary

router = APIRouter(prefix="/clients", tags=["admin"])


@router.get("/{client_id}/invitations", response_model=ClientInvitationsResponse)
def list_client_invitations(
    client_id: str,
    status: str = Query(default="ALL"),
    q: str | None = Query(default=None),
    sort: str = Query(default="created_at_desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ClientInvitationsResponse:
    now = datetime.now(timezone.utc)
    query = db.query(ClientInvitation).filter(ClientInvitation.client_id == client_id)

    status_upper = status.upper().strip()
    if status_upper not in {"ALL", "PENDING", "ACCEPTED", "REVOKED", "EXPIRED"}:
        raise HTTPException(status_code=400, detail="invalid_status")

    if status_upper == "EXPIRED":
        query = query.filter(ClientInvitation.status == "PENDING", ClientInvitation.expires_at < now)
    elif status_upper != "ALL":
        query = query.filter(ClientInvitation.status == status_upper)

    if q:
        query = query.filter(func.lower(ClientInvitation.email).contains(q.strip().lower()))

    total = query.count()

    if sort == "created_at_desc":
        query = query.order_by(ClientInvitation.created_at.desc())
    elif sort == "created_at_asc":
        query = query.order_by(ClientInvitation.created_at.asc())
    elif sort == "expires_at_asc":
        query = query.order_by(ClientInvitation.expires_at.asc(), ClientInvitation.created_at.desc())
    else:
        raise HTTPException(status_code=400, detail="invalid_sort")

    rows = query.offset(offset).limit(limit).all()
    return ClientInvitationsResponse(
        items=[
            ClientInvitationSummary(
                invitation_id=str(item.id),
                email=item.email,
                role=(item.roles or [None])[0],
                roles=item.roles or [],
                status="EXPIRED" if item.status == "PENDING" and item.expires_at and item.expires_at < now else str(item.status),
                expires_at=item.expires_at,
                resent_count=int(item.resent_count or 0),
                last_sent_at=item.last_sent_at,
                created_at=item.created_at,
            )
            for item in rows
        ],
        total=total,
    )


@router.post("/invitations/{invitation_id}/resend", response_model=ClientInvitationActionResponse)
def admin_resend_invitation(
    invitation_id: str,
    _: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ClientInvitationActionResponse:
    invitation = db.query(ClientInvitation).filter(ClientInvitation.id == invitation_id).one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="invite_not_found")
    if invitation.status != "PENDING":
        raise HTTPException(status_code=409, detail="invite_not_pending")

    now = datetime.now(timezone.utc)
    if invitation.expires_at and invitation.expires_at < now:
        raise HTTPException(status_code=409, detail="invite_expired")

    throttle_minutes = max(int(os.getenv("CLIENT_INVITE_RESEND_THROTTLE_MINUTES", "3")), 1)
    if invitation.last_sent_at and (now - invitation.last_sent_at) < timedelta(minutes=throttle_minutes):
        raise HTTPException(status_code=429, detail="invite_resend_throttled")

    invitation.resent_count = int(invitation.resent_count or 0) + 1
    invitation.last_sent_at = now
    invitation.updated_at = now
    db.commit()
    return ClientInvitationActionResponse(status="ok", resent_count=int(invitation.resent_count or 0))


@router.post("/invitations/{invitation_id}/revoke", response_model=ClientInvitationActionResponse)
def admin_revoke_invitation(
    invitation_id: str,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ClientInvitationActionResponse:
    invitation = db.query(ClientInvitation).filter(ClientInvitation.id == invitation_id).one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="invite_not_found")
    if invitation.status != "PENDING":
        raise HTTPException(status_code=409, detail="invite_not_pending")

    invitation.status = "REVOKED"
    invitation.revoked_at = datetime.now(timezone.utc)
    invitation.revoked_by_user_id = str(token.get("user_id") or token.get("sub") or "admin")
    invitation.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ClientInvitationActionResponse(status="ok")
