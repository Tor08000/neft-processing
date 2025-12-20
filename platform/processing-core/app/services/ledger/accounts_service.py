from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.account import Account, AccountOwnerType, AccountType
from app.repositories.accounts_repository import AccountsRepository


class AccountsService:
    """Facade for managing ledger accounts for different owners."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = AccountsRepository(db)

    def get_or_create_owner_account(
        self,
        *,
        owner_type: AccountOwnerType,
        owner_id: str,
        account_type: AccountType,
        currency: str,
        client_id: str | None = None,
        card_id: str | None = None,
        tariff_id: str | None = None,
    ) -> Account:
        resolved_client = client_id or owner_id
        return self.repo.get_or_create_account(
            client_id=resolved_client,
            owner_type=owner_type,
            owner_id=owner_id,
            currency=currency,
            account_type=account_type,
            card_id=card_id,
            tariff_id=tariff_id,
        )
