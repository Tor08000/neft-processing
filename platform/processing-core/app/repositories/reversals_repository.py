from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.reversal import Reversal, ReversalStatus
from app.models.refund_request import SettlementPolicy


class ReversalsRepository:
    """Persistence layer for reversals."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_idempotency(self, idempotency_key: str) -> Reversal | None:
        return (
            self.db.query(Reversal)
            .filter(Reversal.idempotency_key == idempotency_key)
            .one_or_none()
        )

    def create(
        self,
        *,
        operation_id: UUID,
        operation_business_id: str,
        reason: str | None,
        initiator: str | None,
        idempotency_key: str,
        settlement_policy: SettlementPolicy,
    ) -> Reversal:
        reversal = Reversal(
            operation_id=operation_id,
            operation_business_id=operation_business_id,
            reason=reason,
            initiator=initiator,
            idempotency_key=idempotency_key,
            settlement_policy=settlement_policy,
        )
        self.db.add(reversal)
        self.db.flush()
        return reversal

    def mark_posted(self, reversal: Reversal, posting_id: UUID) -> Reversal:
        reversal.status = ReversalStatus.POSTED
        reversal.posted_posting_id = posting_id
        reversal.updated_at = datetime.utcnow()
        self.db.add(reversal)
        return reversal

    def mark_failed(self, reversal: Reversal) -> Reversal:
        reversal.status = ReversalStatus.FAILED
        reversal.updated_at = datetime.utcnow()
        self.db.add(reversal)
        return reversal
