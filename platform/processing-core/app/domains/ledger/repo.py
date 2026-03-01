from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.ledger.models import LedgerAccountBalanceV1, LedgerAccountV1, LedgerEntryV1, LedgerLineV1


class LedgerRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_entry_by_idempotency(self, idempotency_key: str) -> LedgerEntryV1 | None:
        return self.db.execute(select(LedgerEntryV1).where(LedgerEntryV1.idempotency_key == idempotency_key)).scalar_one_or_none()

    def get_entry(self, entry_id: str):
        return self.db.get(LedgerEntryV1, entry_id)

    def get_lines(self, entry_id: str) -> list[LedgerLineV1]:
        return list(self.db.execute(select(LedgerLineV1).where(LedgerLineV1.entry_id == entry_id).order_by(LedgerLineV1.line_no)).scalars())

    def get_or_create_account(self, *, account_code: str, account_type: str, owner_type: str, owner_id: str | None, currency: str) -> LedgerAccountV1:
        account = self.db.execute(
            select(LedgerAccountV1).where(
                LedgerAccountV1.account_code == account_code,
                LedgerAccountV1.owner_type == owner_type,
                LedgerAccountV1.owner_id == owner_id,
                LedgerAccountV1.currency == currency,
            )
        ).scalar_one_or_none()
        if account:
            return account
        account = LedgerAccountV1(
            account_code=account_code,
            account_type=account_type,
            owner_type=owner_type,
            owner_id=owner_id,
            currency=currency,
            status="ACTIVE",
        )
        self.db.add(account)
        self.db.flush()
        return account

    def create_entry(self, payload: dict) -> LedgerEntryV1:
        entry = LedgerEntryV1(**payload)
        self.db.add(entry)
        self.db.flush()
        return entry

    def create_lines(self, lines: list[dict]) -> list[LedgerLineV1]:
        mapped = [LedgerLineV1(**line) for line in lines]
        self.db.add_all(mapped)
        self.db.flush()
        return mapped

    def upsert_balance(self, *, account_id, currency: str, delta: Decimal) -> None:
        row = self.db.get(LedgerAccountBalanceV1, {"account_id": account_id, "currency": currency})
        if row is None:
            row = LedgerAccountBalanceV1(account_id=account_id, currency=currency, balance=Decimal("0"))
            self.db.add(row)
            self.db.flush()
        row.balance = Decimal(str(row.balance)) + delta
        row.updated_at = datetime.now(timezone.utc)
