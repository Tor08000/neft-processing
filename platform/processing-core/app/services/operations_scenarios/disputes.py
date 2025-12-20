from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.account import AccountOwnerType, AccountType
from app.models.account import AccountBalance
from app.models.dispute import Dispute, DisputeEventType, DisputeStatus
from app.models.financial_adjustment import FinancialAdjustmentKind, RelatedEntityType
from app.models.ledger_entry import LedgerDirection
from app.models.operation import Operation
from app.models.posting_batch import PostingBatchType
from app.models.refund_request import SettlementPolicy
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.adjustments_repository import AdjustmentsRepository
from app.repositories.disputes_repository import DisputesRepository
from app.services.ledger.posting_engine import PostingEngine, PostingLine


@dataclass
class DisputeResult:
    dispute: Dispute
    posting_id: UUID | None = None
    adjustment_id: UUID | None = None


class DisputeStateError(Exception):
    """Raised when an invalid state transition is attempted."""

    code = "DISPUTE_STATE_ERROR"


class DisputeService:
    """Simplified dispute / chargeback-like flow with holds and refunds."""

    def __init__(self, db: Session):
        self.db = db
        self.accounts_repo = AccountsRepository(db)
        self.disputes_repo = DisputesRepository(db)
        self.adjustments_repo = AdjustmentsRepository(db)
        self.posting_engine = PostingEngine(db)

    def open_dispute(
        self,
        *,
        operation: Operation,
        amount: int,
        initiator: str | None,
        idempotency_key: str,
        fee_amount: int = 0,
        place_hold: bool = False,
    ) -> DisputeResult:
        dispute = self.disputes_repo.create_dispute(
            operation_id=operation.id,
            operation_business_id=operation.operation_id,
            disputed_amount=amount,
            currency=operation.currency,
            initiator=initiator,
            fee_amount=fee_amount,
        )
        posting_id = None
        if place_hold:
            posting_id = self._place_hold(operation, amount, idempotency_key=f"{idempotency_key}:hold")
            self.disputes_repo.set_hold(dispute, posting_id)
            self.disputes_repo.add_event(
                dispute.id,
                DisputeEventType.HOLD_PLACED,
                actor=initiator,
                payload={"amount": amount},
            )
        self.db.commit()
        self.db.refresh(dispute)
        return DisputeResult(dispute=dispute, posting_id=posting_id)

    def move_to_review(self, dispute: Dispute, actor: str | None = None) -> Dispute:
        if dispute.status != DisputeStatus.OPEN:
            raise DisputeStateError(f"Cannot move dispute {dispute.id} from {dispute.status} to UNDER_REVIEW")
        self.disputes_repo.set_status(dispute, DisputeStatus.UNDER_REVIEW)
        self.disputes_repo.add_event(dispute.id, DisputeEventType.MOVED_TO_REVIEW, actor=actor, payload={})
        self.db.commit()
        return dispute

    def accept(
        self,
        *,
        dispute: Dispute,
        operation: Operation,
        initiator: str | None,
        idempotency_key: str,
        settlement_closed: bool = False,
        adjustment_date: date | None = None,
    ) -> DisputeResult:
        if dispute.status not in {DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW}:
            raise DisputeStateError(f"Cannot accept dispute from {dispute.status}")

        refund_amount = dispute.disputed_amount
        posting_type = PostingBatchType.ADJUSTMENT if settlement_closed else PostingBatchType.REFUND
        use_reserve = dispute.hold_placed
        refund_lines = (
            self._adjustment_refund_lines(operation, refund_amount)
            if settlement_closed
            else self._refund_from_reserve_lines(operation, refund_amount, use_reserve=use_reserve)
        )
        refund_posting = self.posting_engine.apply_posting(
            operation_id=operation.id,
            posting_type=posting_type,
            idempotency_key=f"{idempotency_key}:refund",
            lines=refund_lines,
        )
        self.disputes_repo.set_resolution_posting(dispute, refund_posting.posting_id)
        if dispute.hold_placed:
            dispute.hold_placed = False
            self._clear_holds(
                [
                    self._dispute_reserve(operation.currency),
                    self._partner_payable(operation),
                ]
            )
        self.disputes_repo.set_status(dispute, DisputeStatus.ACCEPTED)
        self.disputes_repo.add_event(
            dispute.id,
            DisputeEventType.ACCEPTED,
            actor=initiator,
            payload={"amount": refund_amount},
        )
        self.disputes_repo.add_event(
            dispute.id,
            DisputeEventType.REFUND_POSTED,
            actor=initiator,
            payload={"posting_id": str(refund_posting.posting_id)},
        )

        fee_posting_id = None
        if dispute.fee_amount and dispute.fee_amount > 0:
            fee_posting = self.posting_engine.apply_posting(
                operation_id=operation.id,
                posting_type=PostingBatchType.ADJUSTMENT if settlement_closed else PostingBatchType.ADJUSTMENT,
                idempotency_key=f"{idempotency_key}:fee",
                lines=self._fee_lines(operation, dispute.fee_amount, use_reserve=use_reserve),
            )
            fee_posting_id = fee_posting.posting_id
            self.disputes_repo.add_event(
                dispute.id,
                DisputeEventType.FEE_POSTED,
                actor=initiator,
                payload={"posting_id": str(fee_posting_id), "amount": dispute.fee_amount},
            )

        adjustment_id = None
        if settlement_closed:
            effective_date = adjustment_date or date.today()
            adj_key = f"{idempotency_key}:adjustment"
            existing_adj = self.adjustments_repo.get_by_idempotency(adj_key)
            if existing_adj:
                adjustment_id = existing_adj.id
            else:
                adjustment = self.adjustments_repo.create(
                    kind=FinancialAdjustmentKind.DISPUTE_ADJUSTMENT,
                    related_entity_type=RelatedEntityType.DISPUTE,
                    related_entity_id=dispute.id,
                    operation_id=operation.id,
                    amount=refund_amount,
                    currency=operation.currency,
                    effective_date=effective_date,
                    idempotency_key=adj_key,
                )
                adjustment_id = adjustment.id

        self.db.commit()
        self.db.refresh(dispute)
        return DisputeResult(dispute=dispute, posting_id=refund_posting.posting_id, adjustment_id=adjustment_id)

    def reject(self, dispute: Dispute, actor: str | None, idempotency_key: str) -> DisputeResult:
        if dispute.status not in {DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW}:
            raise DisputeStateError(f"Cannot reject dispute from {dispute.status}")
        posting_id = None
        if dispute.hold_placed:
            posting_id = self._release_hold(dispute, idempotency_key=f"{idempotency_key}:release")
            self.disputes_repo.add_event(dispute.id, DisputeEventType.HOLD_RELEASED, actor=actor, payload={})
        self.disputes_repo.set_status(dispute, DisputeStatus.REJECTED)
        self.disputes_repo.add_event(dispute.id, DisputeEventType.REJECTED, actor=actor, payload={})
        self.db.commit()
        return DisputeResult(dispute=dispute, posting_id=posting_id)

    def close(self, dispute: Dispute, actor: str | None) -> Dispute:
        if dispute.status not in {DisputeStatus.ACCEPTED, DisputeStatus.REJECTED}:
            raise DisputeStateError(f"Cannot close dispute from {dispute.status}")
        self.disputes_repo.set_status(dispute, DisputeStatus.CLOSED)
        self.disputes_repo.add_event(dispute.id, DisputeEventType.CLOSED, actor=actor, payload={})
        self.db.commit()
        return dispute

    # Posting helpers -------------------------------------------------
    def _partner_payable(self, operation: Operation) -> int:
        return self.accounts_repo.get_or_create_account(
            client_id=operation.merchant_id,
            owner_type=AccountOwnerType.PARTNER,
            owner_id=operation.merchant_id,
            currency=operation.currency,
            account_type=AccountType.TECHNICAL,
            tariff_id="PARTNER_PAYABLE",
        ).id

    def _dispute_reserve(self, currency: str) -> int:
        return self.accounts_repo.get_or_create_account(
            client_id="platform",
            owner_type=AccountOwnerType.PLATFORM,
            owner_id="platform",
            currency=currency,
            account_type=AccountType.TECHNICAL,
            tariff_id="DISPUTE_RESERVE",
        ).id

    def _client_main(self, operation: Operation) -> int:
        return self.accounts_repo.get_or_create_account(
            client_id=operation.client_id,
            owner_type=AccountOwnerType.CLIENT,
            owner_id=operation.client_id,
            currency=operation.currency,
            account_type=AccountType.CLIENT_MAIN,
        ).id

    def _platform_adjustment(self, currency: str) -> int:
        return self.accounts_repo.get_or_create_account(
            client_id="platform",
            owner_type=AccountOwnerType.PLATFORM,
            owner_id="platform",
            currency=currency,
            account_type=AccountType.TECHNICAL,
            tariff_id="PLATFORM_ADJUSTMENT",
        ).id

    def _place_hold(self, operation: Operation, amount: int, idempotency_key: str) -> UUID:
        payable = self._partner_payable(operation)
        reserve = self._dispute_reserve(operation.currency)
        posting = self.posting_engine.apply_posting(
            operation_id=operation.id,
            posting_type=PostingBatchType.DISPUTE_HOLD,
            idempotency_key=idempotency_key,
            lines=[
                PostingLine(account_id=payable, direction=LedgerDirection.DEBIT, amount=amount, currency=operation.currency),
                PostingLine(account_id=reserve, direction=LedgerDirection.CREDIT, amount=amount, currency=operation.currency),
            ],
        )
        return posting.posting_id

    def _release_hold(self, dispute: Dispute, idempotency_key: str) -> UUID:
        # We rely on the operation snapshot to determine accounts; fetching operation via DB for safety
        operation = (
            self.db.query(Operation)
            .filter(Operation.id == dispute.operation_id)
            .one()
        )
        payable = self._partner_payable(operation)
        reserve = self._dispute_reserve(operation.currency)
        posting = self.posting_engine.apply_posting(
            operation_id=operation.id,
            posting_type=PostingBatchType.DISPUTE_RELEASE,
            idempotency_key=idempotency_key,
            lines=[
                PostingLine(account_id=reserve, direction=LedgerDirection.DEBIT, amount=dispute.disputed_amount, currency=operation.currency),
                PostingLine(account_id=payable, direction=LedgerDirection.CREDIT, amount=dispute.disputed_amount, currency=operation.currency),
            ],
        )
        self.disputes_repo.release_hold(dispute, posting.posting_id)
        return posting.posting_id

    def _refund_from_reserve_lines(self, operation: Operation, amount: int, *, use_reserve: bool) -> list[PostingLine]:
        source_account = (
            self._dispute_reserve(operation.currency) if use_reserve else self._partner_payable(operation)
        )
        client = self._client_main(operation)
        return [
            PostingLine(account_id=source_account, direction=LedgerDirection.DEBIT, amount=amount, currency=operation.currency),
            PostingLine(account_id=client, direction=LedgerDirection.CREDIT, amount=amount, currency=operation.currency),
        ]

    def _adjustment_refund_lines(self, operation: Operation, amount: int) -> list[PostingLine]:
        platform_account = self._platform_adjustment(operation.currency)
        client = self._client_main(operation)
        return [
            PostingLine(account_id=platform_account, direction=LedgerDirection.DEBIT, amount=amount, currency=operation.currency),
            PostingLine(account_id=client, direction=LedgerDirection.CREDIT, amount=amount, currency=operation.currency),
        ]

    def _fee_lines(self, operation: Operation, amount: int, *, use_reserve: bool) -> list[PostingLine]:
        source_account = (
            self._dispute_reserve(operation.currency) if use_reserve else self._partner_payable(operation)
        )
        revenue_account = self.accounts_repo.get_or_create_account(
            client_id="platform",
            owner_type=AccountOwnerType.PLATFORM,
            owner_id="platform",
            currency=operation.currency,
            account_type=AccountType.TECHNICAL,
            tariff_id="DISPUTE_FEE_REVENUE",
        ).id
        return [
            PostingLine(account_id=source_account, direction=LedgerDirection.DEBIT, amount=amount, currency=operation.currency),
            PostingLine(account_id=revenue_account, direction=LedgerDirection.CREDIT, amount=amount, currency=operation.currency),
        ]

    def _clear_holds(self, account_ids: list[int]) -> None:
        for acc_id in account_ids:
            balance = (
                self.db.query(AccountBalance)
                .filter(AccountBalance.account_id == acc_id)
                .one_or_none()
            )
            if balance:
                balance.hold_balance = Decimal("0")
                balance.available_balance = Decimal(balance.current_balance or 0)
                self.db.add(balance)
