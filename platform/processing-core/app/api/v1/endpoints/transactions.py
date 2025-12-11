from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from uuid import UUID
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.operations import OperationSchema
from app.models.operation import OperationStatus
from app.schemas.transactions import (
    AuthorizeRequest,
    AuthorizeResponse,
    CaptureRequest,
    CommitRequest,
    RefundOperationRequest,
    RefundRequest,
    ReverseRequest,
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
from app.services.transactions_service import (
    AmountExceeded,
    InvalidOperationState,
    authorize_operation,
    commit_operation,
    reverse_operation,
    refund_operation as service_refund,
    serialize_operation,
)

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["transactions"],
)


@router.post("/authorize", response_model=AuthorizeResponse)
def authorize(body: AuthorizeRequest, db: Session = Depends(get_db)) -> AuthorizeResponse:
    operation = authorize_operation(
        db,
        client_id=body.client_id,
        card_id=body.card_id,
        terminal_id=body.terminal_id,
        merchant_id=body.merchant_id,
        tariff_id=body.tariff_id,
        product_id=body.product_id,
        product_type=body.product_type,
        amount=body.amount,
        currency=body.currency,
        ext_operation_id=body.ext_operation_id,
        quantity=body.quantity,
        unit_price=body.unit_price,
        mcc=body.mcc,
        product_category=body.product_category,
        tx_type=body.tx_type,
        client_group_id=body.client_group_id,
        card_group_id=body.card_group_id,
    )
    return AuthorizeResponse(
        approved=operation.status in {
            OperationStatus.AUTHORIZED,
            OperationStatus.APPROVED,
            OperationStatus.POSTED,
        },
        operation_id=operation.operation_id,
        status=operation.status,
        auth_code=operation.auth_code,
        response_code=operation.response_code,
        response_message=operation.response_message,
        risk_result=operation.risk_result,
        risk_score=operation.risk_score,
        limit_check_result=operation.limit_check_result,
    )


@router.post("/commit", response_model=OperationSchema)
def commit(body: CommitRequest, db: Session = Depends(get_db)) -> OperationSchema:
    try:
        op = commit_operation(db, operation_id=body.operation_id, amount=body.amount, quantity=body.quantity)
    except AmountExceeded as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except InvalidOperationState as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return serialize_operation(op)


@router.post("/reverse", response_model=OperationSchema)
def reverse(body: ReverseRequest, db: Session = Depends(get_db)) -> OperationSchema:
    try:
        op = reverse_operation(db, operation_id=body.operation_id, reason=body.reason)
    except InvalidOperationState as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return serialize_operation(op)


@router.post("/refund", response_model=OperationSchema)
def refund(body: RefundOperationRequest, db: Session = Depends(get_db)) -> OperationSchema:
    try:
        op = service_refund(
            db,
            original_operation_id=body.operation_id,
            amount=body.amount,
            reason=body.reason,
        )
    except AmountExceeded as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except InvalidOperationState as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return serialize_operation(op)


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
