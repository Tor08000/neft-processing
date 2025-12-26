from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerDirection, LedgerEntry
from app.models.posting_batch import PostingBatch, PostingBatchStatus, PostingBatchType
from app.repositories.ledger_repository import LedgerRepository
from app.services.ledger.balance_service import BalanceService
from app.services.finance_invariants import FinancialInvariantChecker, FinancialInvariantViolation


@dataclass(frozen=True)
class PostingLine:
    account_id: int
    direction: LedgerDirection
    amount: Decimal
    currency: str
    metadata: dict | None = None


@dataclass
class PostingResult:
    posting_id: UUID
    batch_id: UUID
    entries: list[LedgerEntry]
    balances: dict[int, dict[str, Decimal]]


class PostingInvariantError(FinancialInvariantViolation):
    """Raised when posting batch violates invariants."""

    code = "POSTING_INVARIANT_VIOLATION"


class PostingEngine:
    """Applies double-entry postings with idempotency guarantees."""

    def __init__(self, db: Session):
        self.db = db
        self.ledger_repo = LedgerRepository(db)
        self.balance_service = BalanceService(db)

    def apply_posting(
        self,
        *,
        operation_id: UUID | None,
        posting_type: PostingBatchType,
        idempotency_key: str,
        lines: Sequence[PostingLine],
        metadata: dict | None = None,
    ) -> PostingResult:
        existing_batch = (
            self.db.query(PostingBatch)
            .filter(PostingBatch.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing_batch:
            entries = (
                self.db.query(LedgerEntry)
                .filter(LedgerEntry.posting_id == existing_batch.id)
                .order_by(LedgerEntry.id.asc())
                .all()
            )
            balances = self.balance_service.snapshot_balances([e.account_id for e in entries])
            return PostingResult(
                posting_id=existing_batch.id,
                batch_id=existing_batch.id,
                entries=entries,
                balances=balances,
            )

        posting_id = uuid4()
        checker = FinancialInvariantChecker(self.db)
        serialized_lines = [
            {
                "account_id": line.account_id,
                "direction": line.direction,
                "amount": Decimal(str(line.amount)),
                "currency": line.currency,
            }
            for line in lines
        ]
        try:
            checker.check_ledger_lines(lines=serialized_lines, posting_id=posting_id)
        except FinancialInvariantViolation as exc:
            raise PostingInvariantError(
                entity_type=exc.entity_type,
                entity_id=exc.entity_id,
                invariant_name=exc.invariant_name,
                expected=exc.expected,
                actual=exc.actual,
                ledger_transaction_id=exc.ledger_transaction_id,
            ) from exc
        batch = PostingBatch(
            id=posting_id,
            operation_id=operation_id,
            posting_type=posting_type,
            status=PostingBatchStatus.APPLIED,
            idempotency_key=idempotency_key,
        )

        created_entries: list[LedgerEntry] = []

        try:
            for line in lines:
                before = self.balance_service.current_balance(line.account_id)
                after = (
                    before
                    if posting_type in {
                        PostingBatchType.AUTH,
                        PostingBatchType.HOLD,
                        PostingBatchType.DISPUTE_HOLD,
                        PostingBatchType.DISPUTE_RELEASE,
                    }
                    else before + line.amount
                    if line.direction == LedgerDirection.CREDIT
                    else before - line.amount
                )
                new_entry = self.ledger_repo.post_entry(
                    account_id=line.account_id,
                    operation_id=operation_id,
                    posting_id=posting_id,
                    direction=line.direction,
                    amount=line.amount,
                    currency=line.currency,
                    entry_id=uuid4(),
                    balance_before=before,
                    balance_after_override=after,
                    require_operation=False,
                    sync_balance=False,
                    auto_commit=False,
                )
                if line.metadata:
                    new_entry.context = line.metadata
                self.balance_service.apply_entry(new_entry, posting_type=posting_type)
                created_entries.append(new_entry)

            self.db.add(batch)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        balances = self.balance_service.snapshot_balances([e.account_id for e in created_entries])
        return PostingResult(
            posting_id=posting_id,
            batch_id=posting_id,
            entries=created_entries,
            balances=balances,
        )
