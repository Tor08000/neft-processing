from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.bi_sync import BiSyncRunOut
from app.services.audit_service import request_context_from_request
from app.services.bi.sync_runtime import BiSyncError, run_sync
from app.models.bi import BiSyncRunType


router = APIRouter(prefix="/bi/sync", tags=["admin-bi"])


@router.post("/init", response_model=BiSyncRunOut)
def init_sync(
    request: Request,
    db: Session = Depends(get_db),
) -> BiSyncRunOut:
    request_ctx = request_context_from_request(request)
    try:
        run = run_sync(db, run_type=BiSyncRunType.INIT, request_ctx=request_ctx)
    except BiSyncError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BiSyncRunOut.model_validate(run)


@router.post("/run", response_model=BiSyncRunOut)
def run_incremental_sync(
    request: Request,
    db: Session = Depends(get_db),
) -> BiSyncRunOut:
    request_ctx = request_context_from_request(request)
    try:
        run = run_sync(db, run_type=BiSyncRunType.INCREMENTAL, request_ctx=request_ctx)
    except BiSyncError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BiSyncRunOut.model_validate(run)


__all__ = ["router"]
