from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operation import Operation
from app.schemas.admin.operational import ReversalCreate, ReversalResponse
from app.services.operations_scenarios.reversals import ReversalService

router = APIRouter(prefix="/reversals", tags=["admin-reversals"])


@router.post("", response_model=ReversalResponse)
def create_reversal(request: ReversalCreate, db: Session = Depends(get_db)) -> ReversalResponse:
    operation = db.query(Operation).filter(Operation.id == request.operation_id).one_or_none()
    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found")

    service = ReversalService(db)
    result = service.reverse_capture(
        operation=operation,
        reason=request.reason,
        initiator=request.initiator,
        idempotency_key=request.idempotency_key or f"reversal:{uuid.uuid4()}",
        settlement_closed=request.settlement_closed,
        adjustment_date=request.adjustment_date,
    )

    reversal = result.reversal
    return ReversalResponse(
        id=reversal.id,
        operation_id=reversal.operation_id,
        status=reversal.status,
        posting_id=result.posting_id,
        settlement_policy=result.settlement_policy,
        adjustment_id=result.adjustment_id,
        created_at=reversal.created_at,
        updated_at=reversal.updated_at,
    )
