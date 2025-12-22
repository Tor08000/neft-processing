from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.clearing import (
    BuildBatchRequest,
    ClearingBatchOperationOut,
    ClearingBatchOut,
)
from app.services.billing.daily import _default_billing_date
from app.services.clearing import (
    build_clearing_batch_for_period,
    get_batch,
    list_batches,
    mark_batch_confirmed,
    mark_batch_sent,
    mark_batch_failed,
    retry_batch,
)
from app.services.clearing_daily import run_clearing_daily
from app.services.clearing_service import run_admin_clearing

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


@router.post("/run-daily")
async def run_daily_clearing(
    clearing_date: date | None = Query(None),
    idempotency_key: str | None = Query(None),
    db: Session = Depends(get_db),
):
    target_date = clearing_date or date.today()
    scope_key = make_stable_key("clearing_run", {"clearing_date": target_date.isoformat()}, idempotency_key)
    try:
        batches = await ClearingRunService(db).run(clearing_date=target_date, idempotency_key=scope_key)
    except ClearingRunInProgress as exc:
        raise HTTPException(status_code=409, detail="already running") from exc
    resolved_date = target_date or (batches[0].date_from if batches else None)
    return {"created": [batch.id for batch in batches], "clearing_date": str(resolved_date) if resolved_date else None}


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


@router.post("/run")
def run_admin_clearing_endpoint(
    clearing_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    target_date = clearing_date or _default_billing_date()
    result = run_admin_clearing(db, clearing_date=target_date)
    return {"clearing_date": str(target_date), **result}


@router.post("/batches/{batch_id}/mark-sent", response_model=ClearingBatchOut)
def mark_batch_sent_endpoint(batch_id: str, db: Session = Depends(get_db)) -> ClearingBatchOut:
    try:
        batch = mark_batch_sent(db, batch_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc))
    return ClearingBatchOut.model_validate(batch)


@router.post("/batches/{batch_id}/mark-confirmed", response_model=ClearingBatchOut)
def mark_batch_confirmed_endpoint(batch_id: str, db: Session = Depends(get_db)) -> ClearingBatchOut:
    try:
        batch = mark_batch_confirmed(db, batch_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc))
    return ClearingBatchOut.model_validate(batch)


@router.post("/batches/{batch_id}/mark-failed", response_model=ClearingBatchOut)
def mark_batch_failed_endpoint(batch_id: str, db: Session = Depends(get_db)) -> ClearingBatchOut:
    try:
        batch = mark_batch_failed(db, batch_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc))
    return ClearingBatchOut.model_validate(batch)


@router.post("/batches/{batch_id}/retry", response_model=ClearingBatchOut)
def retry_batch_endpoint(batch_id: str, db: Session = Depends(get_db)) -> ClearingBatchOut:
    try:
        batch = retry_batch(db, batch_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc))
    return ClearingBatchOut.model_validate(batch)
