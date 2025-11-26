from datetime import datetime
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operation import Operation
from app.schemas.operations import OperationSchema, OperationTimeline, OperationsPage

router = APIRouter(
    prefix="/api/v1/operations",
    tags=["operations-history"],
)


@router.get("", response_model=OperationsPage)
def list_operations(
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
        None, description="AUTHORIZED, DECLINED, CAPTURED, REFUNDED, REVERSED, etc."
    ),
    parent_operation_id: Optional[str] = Query(None),
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
    if parent_operation_id:
        query = query.filter(Operation.parent_operation_id == parent_operation_id)
    if date_from:
        query = query.filter(Operation.created_at >= date_from)
    if date_to:
        query = query.filter(Operation.created_at <= date_to)

    sort_column_map = {
        "created_at": Operation.created_at,
        "amount": Operation.amount,
        "operation_type": Operation.operation_type,
        "status": Operation.status,
    }
    sort_column = sort_column_map.get(sort_by, Operation.created_at)

    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()
    rows = query.offset(offset).limit(limit).all()

    return OperationsPage(
        items=[OperationSchema.from_orm(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{operation_id}", response_model=OperationSchema)
def get_operation(operation_id: str, db: Session = Depends(get_db)) -> OperationSchema:
    op = db.query(Operation).filter(Operation.operation_id == operation_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="operation not found")

    return OperationSchema.from_orm(op)


@router.get("/{operation_id}/timeline", response_model=OperationTimeline)
def get_operation_timeline(
    operation_id: str, db: Session = Depends(get_db)
) -> OperationTimeline:
    root = (
        db.query(Operation).filter(Operation.operation_id == operation_id).first()
    )
    if not root:
        raise HTTPException(status_code=404, detail="operation not found")

    children = (
        db.query(Operation)
        .filter(Operation.parent_operation_id == root.operation_id)
        .order_by(Operation.created_at.asc())
        .all()
    )

    return OperationTimeline(
        root=OperationSchema.from_orm(root),
        children=[OperationSchema.from_orm(child) for child in children],
    )

