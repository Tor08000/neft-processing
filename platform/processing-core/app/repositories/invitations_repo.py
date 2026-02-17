from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.client_invitations import ClientInvitation


class InvitationsRepo:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, invitation_id: str) -> ClientInvitation | None:
        return self.db.query(ClientInvitation).filter(ClientInvitation.id == invitation_id).one_or_none()

    def add(self, invitation: ClientInvitation) -> None:
        self.db.add(invitation)
