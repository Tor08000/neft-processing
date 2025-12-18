from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.dependencies.schema_guard import ensure_tables_exist, raise_schema_error_if_missing
from app.db import get_db
from app.schemas.operations import OperationSchema, OperationsPage
from app.services import operations_query
from app.services.operations_query import get_operation_timeline

router = APIRouter(
    prefix="/api/v1/operations",
    tags=["operations-history"],
)


@router.get("", response_model=OperationsPage)
def list_operations(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    operation_type: str | None = None,
    status: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    client_id: str | None = None,
    card_id: str | None = None,
    from_created_at: datetime | None = None,
    to_created_at: datetime | None = None,
    min_amount: int | None = Query(None, ge=0),
    max_amount: int | None = Query(None, ge=0),
    mcc: str | None = None,
    product_category: str | None = None,
    tx_type: str | None = None,
    response_code: str | None = None,
    response_codes: List[str] | None = Query(None),
    error_code: List[str] | None = Query(None),
    risk_result: List[str] | None = Query(None),
    risk_level: List[str] | None = Query(None),
    risk_min_score: float | None = Query(None),
    risk_max_score: float | None = Query(None),
    order_by: str = Query("created_at_desc"),
    db: Session = Depends(get_db),
) -> OperationsPage:
    ensure_tables_exist(db, tables=("operations",))
    allowed_ordering = set(operations_query._ORDERING.keys())
    if order_by not in allowed_ordering:
        raise HTTPException(status_code=400, detail="Invalid order_by")

    try:
        rows, total = operations_query.list_operations(
            db,
            limit=limit,
            offset=offset,
            operation_type=operation_type,
            status=status,
            merchant_id=merchant_id,
            terminal_id=terminal_id,
            client_id=client_id,
            card_id=card_id,
            from_created_at=from_created_at,
            to_created_at=to_created_at,
            min_amount=min_amount,
            max_amount=max_amount,
            mcc=mcc,
            product_category=product_category,
            tx_type=tx_type,
            response_code=response_code,
            response_codes=response_codes,
            error_codes=error_code,
            risk_results=risk_result,
            risk_levels=risk_level,
            risk_min_score=risk_min_score,
            risk_max_score=risk_max_score,
            order_by=order_by,
        )
    except DBAPIError as exc:
        raise_schema_error_if_missing(exc)
        raise
    return OperationsPage(items=rows, total=total, limit=limit, offset=offset)


@router.get("/{operation_id}", response_model=OperationSchema)
def get_operation(operation_id: str, db: Session = Depends(get_db)) -> OperationSchema:
    ensure_tables_exist(db, tables=("operations",))
    try:
        timeline = get_operation_timeline(db, operation_id)
    except DBAPIError as exc:
        raise_schema_error_if_missing(exc)
        raise
    if not timeline:
        raise HTTPException(status_code=404, detail="operation not found")

    return OperationSchema.from_orm(timeline[0])


@router.get("/{operation_id}/timeline", response_model=List[OperationSchema])
def get_operation_timeline_endpoint(
    operation_id: str, db: Session = Depends(get_db)
) -> List[OperationSchema]:
    ensure_tables_exist(db, tables=("operations",))
    try:
        operations_chain = get_operation_timeline(db, operation_id)
    except DBAPIError as exc:
        raise_schema_error_if_missing(exc)
        raise
    if not operations_chain:
        raise HTTPException(status_code=404, detail="operation not found")

    return [OperationSchema.from_orm(op) for op in operations_chain]

