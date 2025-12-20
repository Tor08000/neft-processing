from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operation import Operation
from app.schemas.admin.operational import RefundCreate, RefundResponse
from app.services.operations_scenarios.refunds import RefundCapExceeded, RefundService

router = APIRouter(prefix="/refunds", tags=["admin-refunds"])


@router.post("", response_model=RefundResponse)
def create_refund(request: RefundCreate, db: Session = Depends(get_db)) -> RefundResponse:
    operation = db.query(Operation).filter(Operation.id == request.operation_id).one_or_none()
    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found")

    service = RefundService(db)
    try:
        result = service.request_refund(
            operation=operation,
            amount=request.amount,
            reason=request.reason,
            initiator=request.initiator,
            idempotency_key=request.idempotency_key or f"refund:{uuid.uuid4()}",
            settlement_closed=request.settlement_closed,
            adjustment_date=request.adjustment_date,
        )
    except RefundCapExceeded as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    refund = result.refund
    return RefundResponse(
        id=refund.id,
        operation_id=refund.operation_id,
        status=refund.status,
        posting_id=result.posting_id,
        settlement_policy=result.settlement_policy,
        adjustment_id=result.adjustment_id,
        created_at=refund.created_at,
        updated_at=refund.updated_at,
    )
