from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operation import Operation
from app.schemas.operations import OperationsPage

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
)


@router.get("/log", response_model=OperationsPage)
def get_transactions_log(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    card_id: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    merchant_id: Optional[str] = Query(None),
    terminal_id: Optional[str] = Query(None),
    operation_type: Optional[str] = Query(
        None, description="AUTH, CAPTURE, REFUND, REVERSAL"
    ),
    status: Optional[str] = Query(
        None,
        description="AUTHORIZED, DECLINED, CAPTURED, REFUNDED, REVERSED, etc.",
    ),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> OperationsPage:
    query = db.query(Operation)

    if card_id:
        query = query.filter(Operation.card_id == card_id)
    if client_id:
        query = query.filter(Operation.client_id == client_id)
    if merchant_id:
        query = query.filter(Operation.merchant_id == merchant_id)
    if terminal_id:
        query = query.filter(Operation.terminal_id == terminal_id)
    if operation_type:
        query = query.filter(Operation.operation_type == operation_type)
    if status:
        query = query.filter(Operation.status == status)
    if date_from:
        query = query.filter(Operation.created_at >= date_from)
    if date_to:
        query = query.filter(Operation.created_at <= date_to)

    sortable_fields = {
        "created_at": Operation.created_at,
        "amount": Operation.amount,
        "operation_type": Operation.operation_type,
        "status": Operation.status,
    }
    sort_column = sortable_fields.get(sort_by, Operation.created_at)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()
    rows = query.offset(offset).limit(limit).all()

    return OperationsPage(items=rows, total=total, limit=limit, offset=offset)
