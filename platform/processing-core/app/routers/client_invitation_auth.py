from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.client_invitations import ClientInvitation
from app.services.invitations.invitation_tokens import hash_invitation_token

router = APIRouter(prefix="/auth/invitations", tags=["auth"])


class InvitationAcceptRequest(BaseModel):
    token: str


@router.post("/accept")
def accept_invitation(payload: InvitationAcceptRequest, db: Session = Depends(get_db)) -> dict:
    token_hash = hash_invitation_token(payload.token)
    invitation = db.query(ClientInvitation).filter(ClientInvitation.token_hash == token_hash).one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="invite_not_found")
    if invitation.status == "REVOKED" or invitation.revoked_at is not None:
        raise HTTPException(status_code=409, detail="invite_revoked")
    if invitation.status == "ACCEPTED" or getattr(invitation, "used_at", None) is not None:
        raise HTTPException(status_code=409, detail="invite_already_accepted")
    if invitation.expires_at and invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="invite_expired")
    if invitation.status != "PENDING":
        raise HTTPException(status_code=409, detail="invite_not_pending")

    invitation.status = "ACCEPTED"
    invitation.accepted_at = datetime.now(timezone.utc)
    invitation.used_at = datetime.now(timezone.utc)
    invitation.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok"}
