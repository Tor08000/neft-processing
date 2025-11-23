from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.operation import Operation
from app.schemas.operations import OperationOut, OperationsPage

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
    operation_type: Optional[str] = Query(None, description="AUTH, CAPTURE, REFUND, REVERSAL"),
    status: Optional[str] = Query(
        None, description="AUTHORIZED, DECLINED, CAPTURED, REFUNDED, REVERSED, etc."
    ),
    from_dt: Optional[datetime] = Query(None),
    to_dt: Optional[datetime] = Query(None),
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
    if from_dt:
        query = query.filter(Operation.created_at >= from_dt)
    if to_dt:
        query = query.filter(Operation.created_at <= to_dt)

    total = query.count()

    query = query.order_by(Operation.created_at.desc(), Operation.id.desc())
    rows = query.offset(offset).limit(limit).all()

    return OperationsPage(
        items=[OperationOut.from_orm(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{operation_id}", response_model=OperationOut)
def get_operation(operation_id: str, db: Session = Depends(get_db)) -> OperationOut:
    op = db.query(Operation).filter(Operation.operation_id == operation_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="operation not found")

    return OperationOut.from_orm(op)
