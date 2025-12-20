from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.refund_request import RefundRequest, RefundRequestStatus, SettlementPolicy


class RefundsRepository:
    """Persistence layer for refund requests."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_idempotency(self, idempotency_key: str) -> RefundRequest | None:
        return (
            self.db.query(RefundRequest)
            .filter(RefundRequest.idempotency_key == idempotency_key)
            .one_or_none()
        )

    def create(
        self,
        *,
        operation_id: UUID,
        operation_business_id: str,
        amount: int,
        currency: str,
        reason: str | None,
        initiator: str | None,
        idempotency_key: str,
        settlement_policy: SettlementPolicy,
    ) -> RefundRequest:
        refund = RefundRequest(
            operation_id=operation_id,
            operation_business_id=operation_business_id,
            amount=amount,
            currency=currency,
            reason=reason,
            initiator=initiator,
            idempotency_key=idempotency_key,
            settlement_policy=settlement_policy,
        )
        self.db.add(refund)
        self.db.flush()
        return refund

    def mark_posted(self, refund: RefundRequest, posting_id: UUID) -> RefundRequest:
        refund.status = RefundRequestStatus.POSTED
        refund.posted_posting_id = posting_id
        refund.updated_at = datetime.utcnow()
        self.db.add(refund)
        return refund

    def mark_failed(self, refund: RefundRequest) -> RefundRequest:
        refund.status = RefundRequestStatus.FAILED
        refund.updated_at = datetime.utcnow()
        self.db.add(refund)
        return refund
