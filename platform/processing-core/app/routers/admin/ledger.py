from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
)
from app.schemas.admin.ledger import (
    InternalLedgerAccountEntriesResponse,
    InternalLedgerAccountResponse,
    InternalLedgerEntryResponse,
    InternalLedgerHealthResponse,
    InternalLedgerTransactionResponse,
)
from app.services.internal_ledger import InternalLedgerHealthService

router = APIRouter(prefix="/ledger", tags=["admin", "ledger"])


@router.get("/health", response_model=InternalLedgerHealthResponse)
def ledger_health(db: Session = Depends(get_db)) -> InternalLedgerHealthResponse:
    health = InternalLedgerHealthService(db).check()
    return InternalLedgerHealthResponse(
        broken_transactions_count=health.broken_transactions_count,
        missing_postings_count=health.missing_postings_count,
    )


@router.get("/accounts", response_model=list[InternalLedgerAccountResponse])
def list_ledger_accounts(
    tenant_id: int | None = Query(default=None, ge=0),
    client_id: str | None = None,
    account_type: str | None = None,
    currency: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[InternalLedgerAccountResponse]:
    query = db.query(InternalLedgerAccount)
    if tenant_id is not None:
        query = query.filter(InternalLedgerAccount.tenant_id == tenant_id)
    if client_id is not None:
        query = query.filter(InternalLedgerAccount.client_id == client_id)
    if account_type is not None:
        query = query.filter(InternalLedgerAccount.account_type == account_type)
    if currency is not None:
        query = query.filter(InternalLedgerAccount.currency == currency)
    if status is not None:
        query = query.filter(InternalLedgerAccount.status == status)
    accounts = query.order_by(InternalLedgerAccount.created_at.asc()).all()
    return [
        InternalLedgerAccountResponse(
            id=str(account.id),
            tenant_id=account.tenant_id,
            client_id=account.client_id,
            account_type=account.account_type,
            currency=account.currency,
            status=account.status,
            created_at=account.created_at,
        )
        for account in accounts
    ]


@router.get("/accounts/{account_id}/entries", response_model=InternalLedgerAccountEntriesResponse)
def list_account_entries(account_id: str, db: Session = Depends(get_db)) -> InternalLedgerAccountEntriesResponse:
    account = db.query(InternalLedgerAccount).filter(InternalLedgerAccount.id == account_id).one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="ledger account not found")
    entries = (
        db.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.account_id == account.id)
        .order_by(InternalLedgerEntry.created_at.asc(), InternalLedgerEntry.id.asc())
        .all()
    )
    running_balance = 0
    entry_responses: list[InternalLedgerEntryResponse] = []
    for entry in entries:
        delta = entry.amount if entry.direction == InternalLedgerEntryDirection.DEBIT else -entry.amount
        running_balance += delta
        entry_responses.append(
            InternalLedgerEntryResponse(
                id=str(entry.id),
                ledger_transaction_id=str(entry.ledger_transaction_id),
                account_id=str(entry.account_id),
                direction=entry.direction,
                amount=entry.amount,
                currency=entry.currency,
                entry_hash=entry.entry_hash,
                created_at=entry.created_at,
                meta=entry.meta,
                balance_after=running_balance,
            )
        )
    return InternalLedgerAccountEntriesResponse(
        account=InternalLedgerAccountResponse(
            id=str(account.id),
            tenant_id=account.tenant_id,
            client_id=account.client_id,
            account_type=account.account_type,
            currency=account.currency,
            status=account.status,
            created_at=account.created_at,
        ),
        entries=entry_responses,
    )


@router.get("/transactions/{transaction_id}", response_model=InternalLedgerTransactionResponse)
def get_ledger_transaction(transaction_id: str, db: Session = Depends(get_db)) -> InternalLedgerTransactionResponse:
    transaction = (
        db.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.id == transaction_id)
        .one_or_none()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="ledger transaction not found")
    entries = (
        db.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.ledger_transaction_id == transaction.id)
        .order_by(InternalLedgerEntry.created_at.asc(), InternalLedgerEntry.id.asc())
        .all()
    )
    entry_payload = [
        InternalLedgerEntryResponse(
            id=str(entry.id),
            ledger_transaction_id=str(entry.ledger_transaction_id),
            account_id=str(entry.account_id),
            direction=entry.direction,
            amount=entry.amount,
            currency=entry.currency,
            entry_hash=entry.entry_hash,
            created_at=entry.created_at,
            meta=entry.meta,
        )
        for entry in entries
    ]
    return InternalLedgerTransactionResponse(
        id=str(transaction.id),
        tenant_id=transaction.tenant_id,
        transaction_type=transaction.transaction_type,
        external_ref_type=transaction.external_ref_type,
        external_ref_id=transaction.external_ref_id,
        idempotency_key=transaction.idempotency_key,
        total_amount=transaction.total_amount,
        currency=transaction.currency,
        posted_at=transaction.posted_at,
        created_at=transaction.created_at,
        meta=transaction.meta,
        entries=entry_payload,
    )
