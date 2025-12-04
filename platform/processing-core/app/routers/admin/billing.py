from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.billing import BillingSummaryPage
from app.schemas.reports import BillingSummaryItem
from app.models.billing_summary import BillingSummary
from app.models.operation import ProductType
from app.services.reports_billing import finalize_billing_summary
from app.services.billing_service import get_billing_summaries

router = APIRouter(prefix="/billing", tags=["admin"])


@router.get("/summary", response_model=BillingSummaryPage)
def admin_list_billing_summaries(
    date_from: date = Query(...),
    date_to: date = Query(...),
    client_id: str | None = None,
    merchant_id: str | None = None,
    product_type: ProductType | None = None,
    currency: str | None = None,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> BillingSummaryPage:
    items, total = get_billing_summaries(
        db,
        date_from=date_from,
        date_to=date_to,
        client_id=client_id,
        merchant_id=merchant_id,
        product_type=product_type,
        currency=currency,
        limit=limit,
        offset=offset,
    )

    return BillingSummaryPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


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
