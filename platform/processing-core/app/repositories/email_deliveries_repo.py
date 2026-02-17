from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.invitation_email_deliveries import InvitationEmailDelivery


class EmailDeliveriesRepo:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, delivery: InvitationEmailDelivery) -> None:
        self.db.add(delivery)
