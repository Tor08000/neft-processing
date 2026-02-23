from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.account import AccountOwnerType, AccountType
from app.models.ledger_entry import LedgerDirection
from app.models.operation import Operation
from app.models.posting_batch import PostingBatchType
from app.models.refund_request import SettlementPolicy
from app.models.reversal import Reversal, ReversalStatus
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.adjustments_repository import AdjustmentsRepository
from app.repositories.reversals_repository import ReversalsRepository
from app.services.ledger.posting_engine import PostingEngine, PostingLine
from app.models.financial_adjustment import FinancialAdjustmentKind, RelatedEntityType


PLATFORM_OWNER_ID = "00000000-0000-0000-0000-000000000001"


@dataclass
class ReversalResult:
    reversal: Reversal
    posting_id: UUID | None
    settlement_policy: SettlementPolicy
    adjustment_id: UUID | None = None


class ReversalAlreadyExists(Exception):
    """Raised when operation already has a posted reversal."""

    code = "REVERSAL_ALREADY_EXISTS"


class ReversalService:
    """Handles capture reversal with settlement boundary awareness."""

    def __init__(self, db: Session):
        self.db = db
        self.accounts_repo = AccountsRepository(db)
        self.reversals_repo = ReversalsRepository(db)
        self.adjustments_repo = AdjustmentsRepository(db)
        self.posting_engine = PostingEngine(db)

    def reverse_capture(
        self,
        *,
        operation: Operation,
        reason: str | None,
        initiator: str | None,
        idempotency_key: str,
        settlement_closed: bool = False,
        adjustment_date: date | None = None,
    ) -> ReversalResult:
        existing = self.reversals_repo.get_by_idempotency(idempotency_key)
        if existing:
            return ReversalResult(
                reversal=existing,
                posting_id=existing.posted_posting_id,
                settlement_policy=existing.settlement_policy,
            )

        existing_for_operation = (
            self.db.query(Reversal)
            .filter(Reversal.operation_id == operation.id)
            .filter(Reversal.status == ReversalStatus.POSTED)
            .one_or_none()
        )
        if existing_for_operation:
            raise ReversalAlreadyExists(f"operation {operation.id} already reversed")

        settlement_policy = (
            SettlementPolicy.ADJUSTMENT_REQUIRED if settlement_closed else SettlementPolicy.SAME_PERIOD
        )
        reversal = self.reversals_repo.create(
            operation_id=operation.id,
            operation_business_id=operation.operation_id,
            reason=reason,
            initiator=initiator,
            idempotency_key=idempotency_key,
            settlement_policy=settlement_policy,
        )

        amount = operation.captured_amount or 0
        posting_type = PostingBatchType.ADJUSTMENT if settlement_policy == SettlementPolicy.ADJUSTMENT_REQUIRED else PostingBatchType.REVERSAL
        lines = (
            self._adjustment_lines(operation, amount)
            if settlement_policy == SettlementPolicy.ADJUSTMENT_REQUIRED
            else self._reversal_lines(operation, amount)
        )

        posting_result = self.posting_engine.apply_posting(
            operation_id=operation.id,
            posting_type=posting_type,
            idempotency_key=idempotency_key,
            lines=lines,
        )
        self.reversals_repo.mark_posted(reversal, posting_result.posting_id)

        adjustment_id = None
        if settlement_policy == SettlementPolicy.ADJUSTMENT_REQUIRED:
            effective_date = adjustment_date or date.today()
            adj_key = f"adjustment:{idempotency_key}"
            existing_adj = self.adjustments_repo.get_by_idempotency(adj_key)
            if existing_adj:
                adjustment_id = existing_adj.id
            else:
                adjustment = self.adjustments_repo.create(
                    kind=FinancialAdjustmentKind.REVERSAL_ADJUSTMENT,
                    related_entity_type=RelatedEntityType.REVERSAL,
                    related_entity_id=reversal.id,
                    operation_id=operation.id,
                    amount=amount,
                    currency=operation.currency,
                    effective_date=effective_date,
                    idempotency_key=adj_key,
                )
                adjustment_id = adjustment.id

        self.db.commit()
        self.db.refresh(reversal)
        return ReversalResult(
            reversal=reversal,
            posting_id=posting_result.posting_id,
            settlement_policy=settlement_policy,
            adjustment_id=adjustment_id,
        )

    # Account helpers
    def _client_main(self, operation: Operation) -> int:
        return self.accounts_repo.get_or_create_account(
            client_id=operation.client_id,
            owner_type=AccountOwnerType.CLIENT,
            owner_id=operation.client_id,
            currency=operation.currency,
            account_type=AccountType.CLIENT_MAIN,
        ).id

    def _partner_payable(self, operation: Operation) -> int:
        return self.accounts_repo.get_or_create_account(
            client_id=operation.merchant_id,
            owner_type=AccountOwnerType.PARTNER,
            owner_id=operation.merchant_id,
            currency=operation.currency,
            account_type=AccountType.TECHNICAL,
            tariff_id="PARTNER_PAYABLE",
        ).id

    def _platform_adjustment(self, currency: str) -> int:
        return self.accounts_repo.get_or_create_account(
            client_id="platform",
            owner_type=AccountOwnerType.PLATFORM,
            owner_id=PLATFORM_OWNER_ID,
            currency=currency,
            account_type=AccountType.TECHNICAL,
            tariff_id="PLATFORM_ADJUSTMENT",
        ).id

    # Posting lines
    def _reversal_lines(self, operation: Operation, amount: int) -> list[PostingLine]:
        payable = self._partner_payable(operation)
        client = self._client_main(operation)
        return [
            PostingLine(account_id=payable, direction=LedgerDirection.DEBIT, amount=amount, currency=operation.currency),
            PostingLine(account_id=client, direction=LedgerDirection.CREDIT, amount=amount, currency=operation.currency),
        ]

    def _adjustment_lines(self, operation: Operation, amount: int) -> list[PostingLine]:
        platform_account = self._platform_adjustment(operation.currency)
        client = self._client_main(operation)
        return [
            PostingLine(account_id=platform_account, direction=LedgerDirection.DEBIT, amount=amount, currency=operation.currency),
            PostingLine(account_id=client, direction=LedgerDirection.CREDIT, amount=amount, currency=operation.currency),
        ]
