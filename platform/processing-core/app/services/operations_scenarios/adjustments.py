from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.financial_adjustment import (
    FinancialAdjustment,
    FinancialAdjustmentKind,
    RelatedEntityType,
)
from app.repositories.adjustments_repository import AdjustmentsRepository


class AdjustmentService:
    """Helper to register cross-period financial adjustments."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = AdjustmentsRepository(db)

    def ensure_adjustment(
        self,
        *,
        idempotency_key: str,
        kind: FinancialAdjustmentKind,
        related_entity_type: RelatedEntityType,
        related_entity_id: UUID,
        operation_id: UUID,
        amount: int,
        currency: str,
        effective_date: date,
    ) -> FinancialAdjustment:
        existing = self.repo.get_by_idempotency(idempotency_key)
        if existing:
            return existing

        adjustment = self.repo.create(
            kind=kind,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            operation_id=operation_id,
            amount=amount,
            currency=currency,
            effective_date=effective_date,
            idempotency_key=idempotency_key,
        )
        self.db.commit()
        self.db.refresh(adjustment)
        return adjustment
