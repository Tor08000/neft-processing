from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.clearing import (
    ClearingBatchAdminOut,
    ClearingBatchListResponse,
)
from app.services.clearing_service import list_clearing_batches, load_clearing_batch


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


__all__ = ["router"]
