from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.dispute import Dispute, DisputeEvent, DisputeEventType, DisputeStatus


class DisputesRepository:
    """Repository for disputes and their events."""

    def __init__(self, db: Session):
        self.db = db

    def create_dispute(
        self,
        *,
        operation_id: UUID,
        operation_business_id: str,
        disputed_amount: int,
        currency: str,
        initiator: str | None = None,
        fee_amount: int = 0,
    ) -> Dispute:
        dispute = Dispute(
            operation_id=operation_id,
            operation_business_id=operation_business_id,
            disputed_amount=disputed_amount,
            currency=currency,
            fee_amount=fee_amount,
        )
        if initiator:
            dispute.initiator = initiator
        self.db.add(dispute)
        self.db.flush()
        self.add_event(dispute.id, DisputeEventType.OPENED, actor=initiator, payload={})
        return dispute

    def add_event(
        self,
        dispute_id: UUID,
        event_type: DisputeEventType,
        *,
        actor: str | None,
        payload: dict | None,
    ) -> DisputeEvent:
        event = DisputeEvent(
            dispute_id=dispute_id,
            event_type=event_type,
            payload=payload or {},
            actor=actor,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def set_status(self, dispute: Dispute, status: DisputeStatus) -> Dispute:
        dispute.status = status
        dispute.updated_at = datetime.utcnow()
        self.db.add(dispute)
        return dispute

    def set_hold(self, dispute: Dispute, posting_id) -> Dispute:
        dispute.hold_placed = True
        dispute.hold_posting_id = posting_id
        dispute.updated_at = datetime.utcnow()
        self.db.add(dispute)
        return dispute

    def release_hold(self, dispute: Dispute, posting_id) -> Dispute:
        dispute.hold_placed = False
        dispute.hold_posting_id = posting_id
        dispute.updated_at = datetime.utcnow()
        self.db.add(dispute)
        return dispute

    def set_resolution_posting(self, dispute: Dispute, posting_id) -> Dispute:
        dispute.resolution_posting_id = posting_id
        dispute.updated_at = datetime.utcnow()
        self.db.add(dispute)
        return dispute
