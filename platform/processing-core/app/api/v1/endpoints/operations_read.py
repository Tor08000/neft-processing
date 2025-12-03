from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.operations import OperationSchema, OperationsPage
from app.services.operations_query import (
    get_operation_timeline,
    list_operations as query_list_operations,
)

router = APIRouter(
    prefix="/api/v1/operations",
    tags=["operations-history"],
)


@router.get("", response_model=OperationsPage)
def list_operations(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> OperationsPage:
    rows, total = query_list_operations(db, limit=limit, offset=offset)
    return OperationsPage(items=rows, total=total, limit=limit, offset=offset)


@router.get("/{operation_id}", response_model=OperationSchema)
def get_operation(operation_id: str, db: Session = Depends(get_db)) -> OperationSchema:
    timeline = get_operation_timeline(db, operation_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="operation not found")

    return OperationSchema.from_orm(timeline[0])


@router.get("/{operation_id}/timeline", response_model=List[OperationSchema])
def get_operation_timeline_endpoint(
    operation_id: str, db: Session = Depends(get_db)
) -> List[OperationSchema]:
    operations_chain = get_operation_timeline(db, operation_id)
    if not operations_chain:
        raise HTTPException(status_code=404, detail="operation not found")

    return [OperationSchema.from_orm(op) for op in operations_chain]

