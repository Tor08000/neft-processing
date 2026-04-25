from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.account import AccountOwnerType, AccountType
from app.models.ledger_entry import LedgerDirection
from app.models.operation import Operation
from app.models.posting_batch import PostingBatchType
from app.models.refund_request import RefundRequest, SettlementPolicy
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.adjustments_repository import AdjustmentsRepository
from app.repositories.refunds_repository import RefundsRepository
from app.services.ledger.posting_engine import PostingEngine, PostingLine
from app.models.financial_adjustment import FinancialAdjustmentKind, RelatedEntityType


PLATFORM_OWNER_ID = "00000000-0000-0000-0000-000000000001"


@dataclass
class RefundResult:
    refund: RefundRequest
    posting_id: UUID | None
    settlement_policy: SettlementPolicy
    adjustment_id: UUID | None = None


class RefundCapExceeded(Exception):
    """Raised when requested refund exceeds available amount."""

    code = "REFUND_CAP_EXCEEDED"


class RefundAmountInvalid(Exception):
    """Raised when refund amount is zero or negative."""

    code = "REFUND_AMOUNT_INVALID"


class RefundService:
    """Domain service for processing refunds with idempotency and ledger effects."""

    def __init__(self, db: Session):
        self.db = db
        self.accounts_repo = AccountsRepository(db)
        self.refunds_repo = RefundsRepository(db)
        self.adjustments_repo = AdjustmentsRepository(db)
        self.posting_engine = PostingEngine(db)

    def request_refund(
        self,
        *,
        operation: Operation,
        amount: int,
        reason: str | None,
        initiator: str | None,
        idempotency_key: str,
        settlement_closed: bool = False,
        adjustment_date: date | None = None,
    ) -> RefundResult:
        existing = self.refunds_repo.get_by_idempotency(idempotency_key)
        if existing:
            return RefundResult(
                refund=existing,
                posting_id=existing.posted_posting_id,
                settlement_policy=existing.settlement_policy,
            )

        if amount <= 0:
            raise RefundAmountInvalid("refund amount must be positive")

        remaining = (operation.captured_amount or 0) - (operation.refunded_amount or 0)
        if amount > remaining:
            raise RefundCapExceeded(f"Refund {amount} exceeds remaining {remaining}")

        settlement_policy = (
            SettlementPolicy.ADJUSTMENT_REQUIRED if settlement_closed else SettlementPolicy.SAME_PERIOD
        )
        refund = self.refunds_repo.create(
            operation_id=operation.id,
            operation_business_id=operation.operation_id,
            amount=amount,
            currency=operation.currency,
            reason=reason,
            initiator=initiator,
            idempotency_key=idempotency_key,
            settlement_policy=settlement_policy,
        )

        posting_type = PostingBatchType.ADJUSTMENT if settlement_policy == SettlementPolicy.ADJUSTMENT_REQUIRED else PostingBatchType.REFUND
        posting_lines = (
            self._adjustment_lines(operation, amount) if settlement_policy == SettlementPolicy.ADJUSTMENT_REQUIRED else self._refund_lines(operation, amount)
        )

        posting_result = self.posting_engine.apply_posting(
            operation_id=operation.id,
            posting_type=posting_type,
            idempotency_key=idempotency_key,
            lines=posting_lines,
        )
        self.refunds_repo.mark_posted(refund, posting_result.posting_id)
        operation.refunded_amount = (operation.refunded_amount or 0) + amount
        self.db.add(operation)

        adjustment_id = None
        if settlement_policy == SettlementPolicy.ADJUSTMENT_REQUIRED:
            effective_date = adjustment_date or date.today()
            adj_idempotency = f"adjustment:{idempotency_key}"
            existing_adj = self.adjustments_repo.get_by_idempotency(adj_idempotency)
            if existing_adj:
                adjustment_id = existing_adj.id
            else:
                adjustment = self.adjustments_repo.create(
                    kind=FinancialAdjustmentKind.REFUND_ADJUSTMENT,
                    related_entity_type=RelatedEntityType.REFUND,
                    related_entity_id=refund.id,
                    operation_id=operation.id,
                    amount=amount,
                    currency=operation.currency,
                    effective_date=effective_date,
                    idempotency_key=adj_idempotency,
                )
                adjustment_id = adjustment.id

        self.db.commit()
        self.db.refresh(refund)
        return RefundResult(
            refund=refund,
            posting_id=posting_result.posting_id,
            settlement_policy=settlement_policy,
            adjustment_id=adjustment_id,
        )

    # Account helpers -------------------------------------------------
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
            client_id=PLATFORM_OWNER_ID,
            owner_type=AccountOwnerType.PLATFORM,
            owner_id=PLATFORM_OWNER_ID,
            currency=currency,
            account_type=AccountType.TECHNICAL,
            tariff_id="PLATFORM_ADJUSTMENT",
        ).id

    # Posting lines ---------------------------------------------------
    def _refund_lines(self, operation: Operation, amount: int) -> list[PostingLine]:
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
