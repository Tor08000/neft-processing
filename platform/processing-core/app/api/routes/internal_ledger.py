from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps.db import get_db
from app.models.internal_ledger import InternalLedgerEntry
from app.schemas.internal_ledger import (
    InternalLedgerEntryResponse,
    InternalLedgerTransactionRequest,
    InternalLedgerTransactionResponse,
)
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService

router = APIRouter()


@router.post("/internal/ledger/transactions", response_model=InternalLedgerTransactionResponse)
def post_internal_ledger_transaction(
    payload: InternalLedgerTransactionRequest,
    db: Session = Depends(get_db),
) -> InternalLedgerTransactionResponse:
    service = InternalLedgerService(db)
    try:
        result = service.post_transaction(
            tenant_id=payload.tenant_id,
            transaction_type=payload.transaction_type,
            external_ref_type=payload.external_ref_type,
            external_ref_id=payload.external_ref_id,
            idempotency_key=payload.idempotency_key,
            posted_at=payload.posted_at,
            meta=payload.meta,
            entries=[
                InternalLedgerLine(
                    account_type=entry.account_type,
                    client_id=entry.client_id,
                    direction=entry.direction,
                    amount=entry.amount,
                    currency=entry.currency,
                    meta=entry.meta,
                )
                for entry in payload.entries
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.flush()
    ledger_entries = (
        db.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.ledger_transaction_id == result.transaction.id)
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
        for entry in ledger_entries
    ]

    db.commit()
    return InternalLedgerTransactionResponse(
        transaction_id=str(result.transaction.id),
        transaction_type=result.transaction.transaction_type,
        external_ref_type=result.transaction.external_ref_type,
        external_ref_id=result.transaction.external_ref_id,
        idempotency_key=result.transaction.idempotency_key,
        total_amount=result.transaction.total_amount,
        currency=result.transaction.currency,
        posted_at=result.transaction.posted_at,
        created_at=result.transaction.created_at,
        is_replay=result.is_replay,
        entries=entry_payload,
    )
