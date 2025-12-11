from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.account import Account, AccountBalance, AccountStatus
from app.repositories.ledger_repository import LedgerRepository
from app.schemas.admin_accounts import AccountsPage, AccountBalanceSchema, StatementResponse, LedgerEntrySchema

router = APIRouter(tags=["accounts"], dependencies=[Depends(require_admin_user)])


def _serialize_account(account: Account, balance: AccountBalance | None) -> AccountBalanceSchema:
    return AccountBalanceSchema(
        id=account.id,
        client_id=account.client_id,
        card_id=account.card_id,
        tariff_id=account.tariff_id,
        currency=account.currency,
        type=account.type,
        status=account.status,
        balance=balance.current_balance if balance else 0,
    )


@router.get("/accounts", response_model=AccountsPage)
def list_accounts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    client_id: str | None = None,
    status: AccountStatus | None = None,
    db: Session = Depends(get_db),
) -> AccountsPage:
    query = db.query(Account)
    if client_id:
        query = query.filter(Account.client_id == client_id)
    if status:
        query = query.filter(Account.status == status)

    total = query.count()
    accounts = query.order_by(Account.id.asc()).offset(offset).limit(limit).all()

    balance_map = {
        bal.account_id: bal
        for bal in db.query(AccountBalance).filter(AccountBalance.account_id.in_([a.id for a in accounts] or [0]))
    }
    items: List[AccountBalanceSchema] = [
        _serialize_account(account, balance_map.get(account.id)) for account in accounts
    ]
    return AccountsPage(items=items, total=total)


@router.get("/accounts/{account_id}/statement", response_model=StatementResponse)
def get_statement(
    account_id: int,
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
) -> StatementResponse:
    repo = LedgerRepository(db)
    entries = repo.get_entries(account_id, start_date=start_date, end_date=end_date)
    if not entries and db.query(Account).filter(Account.id == account_id).count() == 0:
        raise HTTPException(status_code=404, detail="account not found")
    serialized = [
        LedgerEntrySchema(
            id=e.id,
            operation_id=e.operation_id,
            posted_at=e.posted_at,
            direction=e.direction,
            amount=e.amount,
            currency=e.currency,
            balance_after=e.balance_after,
        )
        for e in entries
    ]
    return StatementResponse(account_id=account_id, entries=serialized)


@router.get("/clients/{client_id}/balances", response_model=List[AccountBalanceSchema])
def get_client_balances(client_id: str, db: Session = Depends(get_db)) -> List[AccountBalanceSchema]:
    accounts = db.query(Account).filter(Account.client_id == client_id).all()
    balance_map = {
        bal.account_id: bal
        for bal in db.query(AccountBalance).filter(AccountBalance.account_id.in_([a.id for a in accounts] or [0]))
    }
    return [_serialize_account(account, balance_map.get(account.id)) for account in accounts]
