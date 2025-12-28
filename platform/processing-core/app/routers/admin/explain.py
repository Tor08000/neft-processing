from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps.db import get_db
from app.schemas.admin.unified_explain import UnifiedExplainResponse, UnifiedExplainView
from app.services.explain.errors import UnifiedExplainNotFound, UnifiedExplainValidationError
from app.services.explain.unified import build_unified_explain

router = APIRouter(prefix="/explain", tags=["admin-explain"])


@router.get("", response_model=UnifiedExplainResponse)
def get_unified_explain(
    fuel_tx_id: str | None = Query(None),
    order_id: str | None = Query(None),
    invoice_id: str | None = Query(None),
    view: UnifiedExplainView = Query(UnifiedExplainView.FULL),
    depth: int = Query(3, ge=1, le=5),
    snapshot: bool = Query(False),
    db: Session = Depends(get_db),
) -> UnifiedExplainResponse:
    provided = [value for value in (fuel_tx_id, order_id, invoice_id) if value]
    if len(provided) != 1:
        raise HTTPException(status_code=400, detail="exactly_one_subject_required")

    try:
        return build_unified_explain(
            db,
            fuel_tx_id=fuel_tx_id,
            order_id=order_id,
            invoice_id=invoice_id,
            view=view,
            depth=depth,
            snapshot=snapshot,
        )
    except UnifiedExplainNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnifiedExplainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = ["router"]
