from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.clearing import (
    BuildBatchRequest,
    ClearingBatchOperationOut,
    ClearingBatchOut,
)
from app.services.clearing import (
    build_clearing_batch_for_period,
    get_batch,
    list_batches,
    mark_batch_confirmed,
    mark_batch_sent,
)

router = APIRouter(prefix="/clearing", tags=["admin"])


@router.get("/batches", response_model=list[ClearingBatchOut])
def list_clearing_batches(
    merchant_id: str | None = None,
    status: str | None = None,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ClearingBatchOut]:
    batches = list_batches(
        db,
        merchant_id=merchant_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    return [ClearingBatchOut.model_validate(batch) for batch in batches]


@router.get("/batches/{batch_id}", response_model=ClearingBatchOut)
def get_clearing_batch(batch_id: str, db: Session = Depends(get_db)) -> ClearingBatchOut:
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch not found")
    # ensure operations loaded
    _ = batch.operations  # noqa: F841
    return ClearingBatchOut.model_validate(batch)


@router.get("/batches/{batch_id}/operations", response_model=list[ClearingBatchOperationOut])
def get_clearing_batch_operations(
    batch_id: str, db: Session = Depends(get_db)
) -> list[ClearingBatchOperationOut]:
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch not found")
    operations = batch.operations or []
    return [ClearingBatchOperationOut.model_validate(op) for op in operations]


@router.post("/batches/build", response_model=ClearingBatchOut)
def build_batch(body: BuildBatchRequest = Body(...), db: Session = Depends(get_db)) -> ClearingBatchOut:
    batch = build_clearing_batch_for_period(
        db,
        date_from=body.date_from,
        date_to=body.date_to,
        merchant_id=body.merchant_id,
    )
    _ = batch.operations  # noqa: F841
    return ClearingBatchOut.model_validate(batch)


@router.post("/batches/{batch_id}/mark-sent", response_model=ClearingBatchOut)
def mark_batch_sent_endpoint(batch_id: str, db: Session = Depends(get_db)) -> ClearingBatchOut:
    try:
        batch = mark_batch_sent(db, batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="batch not found")
    return ClearingBatchOut.model_validate(batch)


@router.post("/batches/{batch_id}/mark-confirmed", response_model=ClearingBatchOut)
def mark_batch_confirmed_endpoint(batch_id: str, db: Session = Depends(get_db)) -> ClearingBatchOut:
    try:
        batch = mark_batch_confirmed(db, batch_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="batch not found")
    return ClearingBatchOut.model_validate(batch)
