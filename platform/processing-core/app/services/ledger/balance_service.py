from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.account import AccountBalance
from app.models.ledger_entry import LedgerDirection, LedgerEntry
from app.models.posting_batch import PostingBatchType


class BalanceService:
    """Encapsulates atomic balance updates for ledger postings."""

    def __init__(self, db: Session):
        self.db = db

    def current_balance(self, account_id: int) -> Decimal:
        balance = (
            self.db.query(AccountBalance)
            .filter(AccountBalance.account_id == account_id)
            .with_for_update(nowait=False)
            .one_or_none()
        )
        if balance is None:
            balance = AccountBalance(account_id=account_id)
            self.db.add(balance)
            self.db.flush()
        return Decimal(balance.current_balance or 0)

    def apply_entry(self, entry: LedgerEntry, *, posting_type: PostingBatchType) -> None:
        balance = (
            self.db.query(AccountBalance)
            .filter(AccountBalance.account_id == entry.account_id)
            .with_for_update(nowait=False)
            .one()
        )
        amount = Decimal(entry.amount)
        if posting_type in {
            PostingBatchType.AUTH,
            PostingBatchType.HOLD,
            PostingBatchType.DISPUTE_HOLD,
            PostingBatchType.DISPUTE_RELEASE,
        }:
            balance.hold_balance = Decimal(balance.hold_balance or 0) + (
                amount if entry.direction == LedgerDirection.DEBIT else -amount
            )
            balance.available_balance = Decimal(balance.available_balance or 0) - (
                amount if entry.direction == LedgerDirection.DEBIT else -amount
            )
            # current balance unchanged for holds
        else:
            current = Decimal(balance.current_balance or 0)
            balance.current_balance = current + amount if entry.direction == LedgerDirection.CREDIT else current - amount
            balance.available_balance = balance.current_balance - Decimal(balance.hold_balance or 0)

        balance.updated_at = entry.posted_at
        self.db.add(balance)

    def snapshot_balances(self, account_ids: list[int]) -> dict[int, dict[str, Decimal]]:
        records = (
            self.db.query(AccountBalance)
            .filter(AccountBalance.account_id.in_(account_ids or [0]))
            .all()
        )
        return {
            bal.account_id: {
                "current": Decimal(bal.current_balance or 0),
                "available": Decimal(bal.available_balance or 0),
                "hold": Decimal(bal.hold_balance or 0),
            }
            for bal in records
        }
