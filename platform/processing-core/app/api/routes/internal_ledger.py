from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps.db import get_db
from app.domains.ledger.errors import IdempotencyMismatch, InvariantViolation
from app.domains.ledger.schemas import LedgerEntryOut, LedgerPostRequest
from app.domains.ledger.service import InternalLedgerService

router = APIRouter(prefix="/internal/ledger", tags=["internal-ledger-v1"])


@router.post("/transactions", response_model=LedgerEntryOut)
def create_transaction(payload: LedgerPostRequest, db: Session = Depends(get_db)) -> LedgerEntryOut:
    service = InternalLedgerService(db)
    try:
        response = service.post_entry(payload)
        db.commit()
        return response
    except IdempotencyMismatch as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvariantViolation as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/entries/{entry_id}", response_model=LedgerEntryOut)
def get_entry(entry_id: str, db: Session = Depends(get_db)) -> LedgerEntryOut:
    return InternalLedgerService(db).get_entry(entry_id)


@router.get("/accounts/balance")
def get_balance(
    account_code: str = Query(...),
    owner_id: str | None = Query(None),
    currency: str = Query("RUB"),
    db: Session = Depends(get_db),
):
    return InternalLedgerService(db).get_balance(account_code=account_code, owner_id=owner_id, currency=currency)
