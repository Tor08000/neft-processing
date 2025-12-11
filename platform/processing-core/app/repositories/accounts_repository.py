from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.account import Account, AccountStatus, AccountType, AccountBalance


class AccountsRepository:
    """Repository for managing accounts lifecycle and lookup."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_account(
        self,
        *,
        client_id: str,
        currency: str,
        account_type: AccountType,
        card_id: str | None = None,
        tariff_id: str | None = None,
        status: AccountStatus = AccountStatus.ACTIVE,
    ) -> Account:
        """Fetch existing account by unique tuple or create a new one."""

        query = (
            self.db.query(Account)
            .filter(Account.client_id == client_id)
            .filter(Account.currency == currency)
            .filter(Account.type == account_type)
        )

        if card_id is None:
            query = query.filter(Account.card_id.is_(None))
        else:
            query = query.filter(Account.card_id == card_id)

        if tariff_id is None:
            query = query.filter(Account.tariff_id.is_(None))
        else:
            query = query.filter(Account.tariff_id == tariff_id)

        account = query.first()
        if account:
            return account

        account = Account(
            client_id=client_id,
            currency=currency,
            type=account_type,
            status=status,
            card_id=card_id,
            tariff_id=tariff_id,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def set_status(self, account_id: int, status: AccountStatus) -> Account:
        """Update account status and return the updated instance."""

        account = self.db.query(Account).filter(Account.id == account_id).one()
        account.status = status
        self.db.commit()
        self.db.refresh(account)
        return account

    def freeze_account(self, account_id: int) -> Account:
        """Mark account as frozen."""

        return self.set_status(account_id, AccountStatus.FROZEN)

    def close_account(self, account_id: int) -> Account:
        """Close account and make it unavailable for posting."""

        return self.set_status(account_id, AccountStatus.CLOSED)

    def get_balance(self, account_id: int) -> AccountBalance:
        """Return current balance snapshot creating one if missing."""

        balance = (
            self.db.query(AccountBalance)
            .filter(AccountBalance.account_id == account_id)
            .one_or_none()
        )
        if balance:
            return balance

        balance = AccountBalance(account_id=account_id)
        self.db.add(balance)
        self.db.commit()
        self.db.refresh(balance)
        return balance
