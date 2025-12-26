from __future__ import annotations

from pydantic import BaseModel


class InternalLedgerHealthResponse(BaseModel):
    broken_transactions_count: int
    missing_postings_count: int
