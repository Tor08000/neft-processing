from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.account import AccountBalance
from app.models.ledger_entry import LedgerDirection, LedgerEntry


class LedgerRepository:
    """Repository for posting ledger entries and fetching statements."""

    def __init__(self, db: Session):
        self.db = db

    def post_entry(
        self,
        *,
        account_id: int,
        operation_id: UUID | None,
        direction: LedgerDirection,
        amount: Decimal | float | int,
        currency: str,
        posted_at: datetime | None = None,
        value_date: date | None = None,
        auto_commit: bool = True,
    ) -> LedgerEntry:
        """Create ledger entry and update account balances."""

        decimal_amount = Decimal(str(amount))
        balance = (
            self.db.query(AccountBalance)
            .filter(AccountBalance.account_id == account_id)
            .one_or_none()
        )
        if balance is None:
            balance = AccountBalance(account_id=account_id)
            self.db.add(balance)
            self.db.flush()

        current = Decimal(balance.current_balance or 0)
        if direction == LedgerDirection.CREDIT:
            new_balance = current + decimal_amount
        else:
            new_balance = current - decimal_amount

        now = posted_at or datetime.now(timezone.utc)
        entry = LedgerEntry(
            account_id=account_id,
            operation_id=operation_id,
            direction=direction,
            amount=decimal_amount,
            currency=currency,
            balance_after=new_balance,
            posted_at=now,
            value_date=value_date,
        )
        self.db.add(entry)

        balance.current_balance = new_balance
        balance.available_balance = new_balance
        balance.updated_at = now
        if auto_commit:
            self.db.commit()
            self.db.refresh(entry)
            self.db.refresh(balance)
        else:
            self.db.flush()
        return entry

    def get_entries(
        self,
        account_id: int,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[LedgerEntry]:
        """Return ordered ledger entries for account in optional period."""

        query = self.db.query(LedgerEntry).filter(LedgerEntry.account_id == account_id)
        if start_date:
            query = query.filter(LedgerEntry.posted_at >= start_date)
        if end_date:
            query = query.filter(LedgerEntry.posted_at <= end_date)
        return query.order_by(LedgerEntry.posted_at.asc(), LedgerEntry.id.asc()).all()
