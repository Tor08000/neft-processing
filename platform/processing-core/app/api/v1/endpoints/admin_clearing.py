from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.clearing import ClearingBatchAdminOut, ClearingBatchListResponse
from app.services.clearing_service import list_clearing_batches, load_clearing_batch
from app.services.clearing_runs import ClearingRunInProgress, ClearingRunService
from app.services.job_locks import make_stable_key


router = APIRouter(
    prefix="/admin/clearing",
    tags=["admin"],
    dependencies=[Depends(require_admin_user)],
)


@router.get("/batches", response_model=ClearingBatchListResponse)
def list_batches_endpoint(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    merchant_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ClearingBatchListResponse:
    batches, total = list_clearing_batches(
        db=db,
        date_from=date_from,
        date_to=date_to,
        merchant_id=merchant_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [ClearingBatchAdminOut.model_validate(batch) for batch in batches]
    return ClearingBatchListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/batches/{batch_id}", response_model=ClearingBatchAdminOut)
def get_batch_endpoint(batch_id: str, db: Session = Depends(get_db)) -> ClearingBatchAdminOut:
    batch = load_clearing_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="batch not found")
    return ClearingBatchAdminOut.model_validate(batch)


@router.post("/run", response_model=ClearingBatchListResponse)
async def run_clearing_endpoint(
    clearing_date: date | None = Query(None),
    date_param: date | None = Query(None, alias="date"),
    idempotency_key: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ClearingBatchListResponse:
    target_date = clearing_date or date_param
    if target_date is None:
        raise HTTPException(status_code=422, detail="clearing_date_required")

    scope_key = make_stable_key("clearing_run", {"clearing_date": target_date.isoformat()}, idempotency_key)
    try:
        batches = await ClearingRunService(db).run(clearing_date=target_date, idempotency_key=scope_key)
    except ClearingRunInProgress as exc:
        raise HTTPException(status_code=409, detail="already running") from exc

    items = [ClearingBatchAdminOut.model_validate(batch) for batch in batches]
    return ClearingBatchListResponse(items=items, total=len(items), limit=len(items), offset=0)


__all__ = ["router"]
