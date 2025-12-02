from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from uuid import UUID
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.operations import OperationSchema
from app.schemas.transactions import (
    CaptureRequest,
    RefundRequest,
    TransactionDetailResponse,
    TransactionsPage,
)
from app.services.operations_query import get_operation_timeline
from app.services.transactions import (
    AmountTooLarge,
    InvalidState,
    OperationNotFound,
    ParentNotFound,
    capture_operation,
    get_transaction,
    list_transactions,
    refund_operation,
    reverse_auth,
)

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["transactions"],
)


@router.get("", response_model=TransactionsPage)
def list_transactions_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    status: str | None = None,
    from_created_at: datetime | None = Query(None, alias="from"),
    to_created_at: datetime | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
) -> TransactionsPage:
    return list_transactions(
        db,
        limit=limit,
        offset=offset,
        client_id=client_id,
        card_id=card_id,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        status=status,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
    )


@router.get("/{transaction_id}", response_model=TransactionDetailResponse)
def get_transaction_endpoint(
    transaction_id: str, db: Session = Depends(get_db)
) -> TransactionDetailResponse:
    transaction = get_transaction(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="transaction not found")

    return transaction


@router.get("/{transaction_id}/timeline", response_model=List[OperationSchema])
def get_transaction_timeline_endpoint(
    transaction_id: str, db: Session = Depends(get_db)
) -> List[OperationSchema]:
    operations_chain = get_operation_timeline(db, transaction_id)
    if not operations_chain:
        raise HTTPException(status_code=404, detail="transaction not found")

    return [OperationSchema.from_orm(op) for op in operations_chain]


@router.post("/transactions/{auth_operation_id}/capture", response_model=OperationSchema)
def capture_transaction_endpoint(
    auth_operation_id: UUID,
    body: CaptureRequest = Body(None),
    db: Session = Depends(get_db),
) -> OperationSchema:
    try:
        operation = capture_operation(db, auth_operation_id=auth_operation_id, amount=body.amount if body else None)
    except ParentNotFound:
        raise HTTPException(status_code=404, detail="operation not found")
    except AmountTooLarge as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except InvalidState as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return OperationSchema.from_orm(operation)


@router.post("/transactions/{capture_operation_id}/refund", response_model=OperationSchema)
def refund_transaction_endpoint(
    capture_operation_id: UUID,
    body: RefundRequest = Body(None),
    db: Session = Depends(get_db),
) -> OperationSchema:
    try:
        operation = refund_operation(
            db,
            captured_operation_id=capture_operation_id,
            amount=body.amount if body else None,
        )
    except ParentNotFound:
        raise HTTPException(status_code=404, detail="operation not found")
    except AmountTooLarge as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except InvalidState as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return OperationSchema.from_orm(operation)


@router.post("/transactions/{auth_operation_id}/reverse", response_model=OperationSchema)
def reverse_transaction_endpoint(
    auth_operation_id: UUID,
    db: Session = Depends(get_db),
) -> OperationSchema:
    try:
        operation = reverse_auth(db, auth_operation_id=auth_operation_id)
    except ParentNotFound:
        raise HTTPException(status_code=404, detail="operation not found")
    except InvalidState as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return OperationSchema.from_orm(operation)
