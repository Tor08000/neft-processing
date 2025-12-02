from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.reports import BillingSummaryItem
from app.models.billing_summary import BillingSummary
from app.services.admin_auth import require_admin
from app.services.reports_billing import (
    finalize_billing_summary,
    get_or_build_summary,
    list_billing_summaries,
)

router = APIRouter(prefix="/admin/billing", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/summary", response_model=list[BillingSummaryItem])
def admin_list_billing_summaries(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: str | None = None,
    status: str | None = None,
    auto_build: bool = False,
    db: Session = Depends(get_db),
) -> list[BillingSummaryItem]:
    summaries = (
        get_or_build_summary(
            db,
            date_from=date_from,
            date_to=date_to,
            merchant_id=merchant_id,
            status=status,
        )
        if auto_build
        else list_billing_summaries(
            db, date_from=date_from, date_to=date_to, merchant_id=merchant_id, status=status
        )
    )
    return [BillingSummaryItem.model_validate(item) for item in summaries]


@router.get("/summary/{summary_id}", response_model=BillingSummaryItem)
def admin_get_summary(summary_id: str, db: Session = Depends(get_db)) -> BillingSummaryItem:
    summary = db.query(BillingSummary).filter_by(id=summary_id).first()
    if summary is None:
        raise HTTPException(status_code=404, detail="summary not found")
    return BillingSummaryItem.model_validate(summary)


@router.post("/summary/{summary_id}/finalize", response_model=BillingSummaryItem)
def admin_finalize_summary(summary_id: str, db: Session = Depends(get_db)) -> BillingSummaryItem:
    try:
        summary = finalize_billing_summary(db, summary_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="summary not found")
    return BillingSummaryItem.model_validate(summary)
