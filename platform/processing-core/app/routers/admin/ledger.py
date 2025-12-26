from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.admin.ledger import InternalLedgerHealthResponse
from app.services.internal_ledger import InternalLedgerHealthService

router = APIRouter(prefix="/ledger", tags=["admin", "ledger"])


@router.get("/health", response_model=InternalLedgerHealthResponse)
def ledger_health(db: Session = Depends(get_db)) -> InternalLedgerHealthResponse:
    health = InternalLedgerHealthService(db).check()
    return InternalLedgerHealthResponse(
        broken_transactions_count=health.broken_transactions_count,
        missing_postings_count=health.missing_postings_count,
    )
