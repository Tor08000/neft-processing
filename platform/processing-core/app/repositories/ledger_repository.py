from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.account import AccountBalance
from app.models.ledger_entry import LedgerDirection, LedgerEntry
from app.models.operation import Operation


class OperationNotFound(Exception):
    """Raised when a referenced operation does not exist."""

    code = "OPERATION_NOT_FOUND"

    def __init__(self, operation_id: UUID):
        super().__init__(self.code)
        self.operation_id = operation_id


class LedgerRepository:
    """Repository for posting ledger entries and fetching statements."""

    def __init__(self, db: Session):
        self.db = db

    def post_entry(
        self,
        *,
        account_id: int,
        operation_id: UUID | None,
        posting_id: UUID | None = None,
        direction: LedgerDirection,
        amount: Decimal | float | int,
        currency: str,
        posted_at: datetime | None = None,
        value_date: date | None = None,
        entry_id: UUID | None = None,
        balance_before: Decimal | None = None,
        balance_after_override: Decimal | None = None,
        require_operation: bool = True,
        sync_balance: bool = True,
        auto_commit: bool = True,
    ) -> LedgerEntry:
        """Create ledger entry and update account balances."""

        decimal_amount = Decimal(str(amount))

        if operation_id is not None and require_operation:
            exists = (
                self.db.query(Operation.id)
                .filter(Operation.id == operation_id)
                .scalar()
            )
            if exists is None:
                raise OperationNotFound(operation_id)

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
        computed_after = (
            balance_after_override
            if balance_after_override is not None
            else current + decimal_amount
            if direction == LedgerDirection.CREDIT
            else current - decimal_amount
        )

        now = posted_at or datetime.now(timezone.utc)
        entry = LedgerEntry(
            account_id=account_id,
            operation_id=operation_id,
            posting_id=posting_id or uuid4(),
            entry_id=entry_id or uuid4(),
            direction=direction,
            amount=decimal_amount,
            currency=currency,
            balance_before=balance_before if balance_before is not None else current,
            balance_after=computed_after,
            posted_at=now,
            value_date=value_date,
        )
        self.db.add(entry)

        if sync_balance:
            balance.current_balance = computed_after
            balance.available_balance = computed_after
            balance.updated_at = now
        if auto_commit:
            self.db.commit()
            self.db.refresh(entry)
            if sync_balance:
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
