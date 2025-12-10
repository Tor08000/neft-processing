from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operation import Operation
from app.schemas.operations import OperationSchema
from app.schemas.admin.dashboard import (
    OperationListResponse,
    OperationShort,
    TransactionListResponse,
    TransactionShort,
)
from app.services.transactions import list_transactions

router = APIRouter(prefix="", tags=["admin"])


_ORDERING_OPERATION = {
    "created_at_desc": (Operation.created_at.desc(), Operation.operation_id.desc()),
    "created_at_asc": (Operation.created_at.asc(), Operation.operation_id.asc()),
    "amount_desc": (Operation.amount.desc(), Operation.operation_id.desc()),
    "amount_asc": (Operation.amount.asc(), Operation.operation_id.asc()),
    "risk_score_desc": (Operation.risk_score.desc(), Operation.operation_id.desc()),
    "risk_score_asc": (Operation.risk_score.asc(), Operation.operation_id.asc()),
}


def _serialize_operations(items: List[Operation]) -> List[OperationShort]:
    return [
        OperationShort(
            operation_id=item.operation_id,
            created_at=item.created_at,
            operation_type=item.operation_type,
            status=item.status,
            merchant_id=item.merchant_id,
            terminal_id=item.terminal_id,
            client_id=item.client_id,
            card_id=item.card_id,
            amount=item.amount,
            currency=item.currency,
            captured_amount=item.captured_amount,
            refunded_amount=item.refunded_amount,
            parent_operation_id=item.parent_operation_id,
            mcc=item.mcc,
            product_code=item.product_code,
            product_category=item.product_category,
            tx_type=item.tx_type,
            daily_limit=item.daily_limit,
            limit_per_tx=item.limit_per_tx,
            used_today=item.used_today,
            new_used_today=item.new_used_today,
            authorized=item.authorized,
            response_code=item.response_code,
            response_message=item.response_message,
            reason=item.reason,
            risk_result=item.risk_result,
            risk_score=item.risk_score,
            risk_flags=(item.risk_payload or {}).get("flags")
            if isinstance(item.risk_payload, dict)
            else None,
            risk_reasons=(item.risk_payload or {}).get("reasons")
            if isinstance(item.risk_payload, dict)
            else None,
            risk_source=(
                (item.risk_payload or {}).get("source")
                if isinstance(item.risk_payload, dict)
                else None
            )
            or ((item.risk_payload or {}).get("engine") if isinstance(item.risk_payload, dict) else None),
        )
        for item in items
    ]


@router.get("/operations", response_model=OperationListResponse)
def list_operations_admin(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    operation_type: str | None = None,
    status: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    client_id: str | None = None,
    card_id: str | None = None,
    from_created_at: datetime | None = None,
    to_created_at: datetime | None = None,
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    min_amount: int | None = Query(None, ge=0),
    max_amount: int | None = Query(None, ge=0),
    order_by: str = Query("created_at_desc"),
    mcc: str | None = None,
    product_category: str | None = None,
    tx_type: str | None = None,
    response_code: str | None = None,
    risk_result: List[str] | None = Query(None),
    risk_min_score: float | None = Query(None),
    risk_max_score: float | None = Query(None),
    db: Session = Depends(get_db),
) -> OperationListResponse:
    if order_by not in _ORDERING_OPERATION:
        raise HTTPException(status_code=400, detail="Invalid order_by")

    query = db.query(Operation)

    if operation_type:
        query = query.filter(Operation.operation_type == operation_type)
    if status:
        query = query.filter(Operation.status == status)
    if merchant_id:
        query = query.filter(Operation.merchant_id == merchant_id)
    if terminal_id:
        query = query.filter(Operation.terminal_id == terminal_id)
    if client_id:
        query = query.filter(Operation.client_id == client_id)
    if card_id:
        query = query.filter(Operation.card_id == card_id)
    if date_from and not from_created_at:
        from_created_at = date_from
    if date_to and not to_created_at:
        to_created_at = date_to

    if from_created_at:
        query = query.filter(Operation.created_at >= from_created_at)
    if to_created_at:
        query = query.filter(Operation.created_at <= to_created_at)
    if min_amount is not None:
        query = query.filter(Operation.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Operation.amount <= max_amount)
    if mcc:
        query = query.filter(Operation.mcc == mcc)
    if product_category:
        query = query.filter(Operation.product_category == product_category)
    if tx_type:
        query = query.filter(Operation.tx_type == tx_type)
    if response_code:
        query = query.filter(Operation.response_code == response_code)
    if risk_result:
        query = query.filter(Operation.risk_result.in_(risk_result))
    if risk_min_score is not None:
        query = query.filter(Operation.risk_score >= risk_min_score)
    if risk_max_score is not None:
        query = query.filter(Operation.risk_score <= risk_max_score)

    total = query.count()
    items: List[Operation] = (
        query.order_by(*_ORDERING_OPERATION[order_by])
        .offset(offset)
        .limit(limit)
        .all()
    )

    serialized = _serialize_operations(items)
    return OperationListResponse(items=serialized, total=total, limit=limit, offset=offset)


_ORDERING_TRANSACTIONS = {
    "created_at_desc": lambda tx: (-tx.created_at.timestamp(), tx.transaction_id),
    "created_at_asc": lambda tx: (tx.created_at.timestamp(), tx.transaction_id),
    "amount_desc": lambda tx: (-tx.authorized_amount, tx.transaction_id),
    "amount_asc": lambda tx: (tx.authorized_amount, tx.transaction_id),
}


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions_admin(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    transaction_status: str | None = Query(None),
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    client_id: str | None = None,
    card_id: str | None = None,
    from_created_at: datetime | None = None,
    to_created_at: datetime | None = None,
    min_amount: int | None = Query(None, ge=0),
    max_amount: int | None = Query(None, ge=0),
    order_by: str = Query("created_at_desc"),
    status: str | None = Query(None),
    product_category: str | None = None,
    mcc: str | None = None,
    tx_type: str | None = None,
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    effective_status = transaction_status or status
    if order_by not in _ORDERING_TRANSACTIONS:
        raise HTTPException(status_code=400, detail="Invalid order_by")

    page = list_transactions(
        db,
        limit=limit,
        offset=offset,
        client_id=client_id,
        card_id=card_id,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        status=effective_status,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
        min_amount=min_amount,
        max_amount=max_amount,
        order_by=order_by,
        product_category=product_category,
        mcc=mcc,
        tx_type=tx_type,
    )

    items = page.items
    total = page.total

    serialized = [
        TransactionShort(
            transaction_id=tx.transaction_id,
            created_at=tx.created_at,
            updated_at=tx.updated_at,
            client_id=tx.client_id,
            card_id=tx.card_id,
            merchant_id=tx.merchant_id,
            terminal_id=tx.terminal_id,
            status=tx.status,
            authorized_amount=tx.authorized_amount,
            captured_amount=tx.captured_amount,
            refunded_amount=tx.refunded_amount,
            currency=tx.currency,
            mcc=tx.mcc,
            product_category=tx.product_category,
            tx_type=tx.tx_type,
        )
        for tx in items
    ]

    return TransactionListResponse(items=serialized, total=total, limit=limit, offset=offset)


@router.get("/operations/{operation_id}", response_model=OperationSchema)
def get_operation(operation_id: str, db: Session = Depends(get_db)) -> OperationSchema:
    operation = db.query(Operation).filter(Operation.operation_id == operation_id).first()
    if operation is None:
        raise HTTPException(status_code=404, detail="operation not found")
    return OperationSchema.from_orm(operation)


@router.get("/operations/{operation_id}/children", response_model=OperationListResponse)
def get_operation_children(
    operation_id: str, db: Session = Depends(get_db)
) -> OperationListResponse:
    items: List[Operation] = (
        db.query(Operation)
        .filter(Operation.parent_operation_id == operation_id)
        .order_by(Operation.created_at.asc(), Operation.operation_id.asc())
        .all()
    )
    serialized = _serialize_operations(items)
    return OperationListResponse(items=serialized, total=len(serialized), limit=len(serialized), offset=0)
