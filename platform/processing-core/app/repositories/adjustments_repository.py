from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.financial_adjustment import (
    FinancialAdjustment,
    FinancialAdjustmentKind,
    FinancialAdjustmentStatus,
    RelatedEntityType,
)


class AdjustmentsRepository:
    """Repository for cross-period financial adjustments."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_idempotency(self, idempotency_key: str) -> FinancialAdjustment | None:
        return (
            self.db.query(FinancialAdjustment)
            .filter(FinancialAdjustment.idempotency_key == idempotency_key)
            .one_or_none()
        )

    def create(
        self,
        *,
        kind: FinancialAdjustmentKind,
        related_entity_type: RelatedEntityType,
        related_entity_id: UUID,
        operation_id: UUID,
        amount: int,
        currency: str,
        effective_date: date,
        idempotency_key: str,
    ) -> FinancialAdjustment:
        adjustment = FinancialAdjustment(
            kind=kind,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            operation_id=operation_id,
            amount=amount,
            currency=currency,
            effective_date=effective_date,
            idempotency_key=idempotency_key,
        )
        self.db.add(adjustment)
        self.db.flush()
        return adjustment

    def mark_posted(self, adjustment: FinancialAdjustment, posting_id: UUID) -> FinancialAdjustment:
        adjustment.status = FinancialAdjustmentStatus.POSTED
        adjustment.posting_id = posting_id
        adjustment.updated_at = datetime.utcnow()
        self.db.add(adjustment)
        return adjustment

    def mark_failed(self, adjustment: FinancialAdjustment) -> FinancialAdjustment:
        adjustment.status = FinancialAdjustmentStatus.FAILED
        adjustment.updated_at = datetime.utcnow()
        self.db.add(adjustment)
        return adjustment
