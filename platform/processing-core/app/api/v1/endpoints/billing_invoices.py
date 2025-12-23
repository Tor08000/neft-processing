from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.billing_invoices import (
    ClosePeriodRequest,
    ClosePeriodResponse,
    InvoiceGenerateResponse,
    InvoiceOut,
)
from app.models.invoice import Invoice
from app.services.billing_invoice_service import close_clearing_period, generate_invoice_for_batch

router = APIRouter(prefix="/api/v1", tags=["billing"])


@router.post("/billing/close-period", response_model=ClosePeriodResponse)
def close_period_endpoint(payload: ClosePeriodRequest, db: Session = Depends(get_db)) -> ClosePeriodResponse:
    try:
        batch = close_clearing_period(
            db,
            period_from=payload.from_date,
            period_to=payload.to_date,
            tenant_id=payload.tenant_id,
        )
    except ValueError as exc:
        if str(exc) == "invalid_period":
            raise HTTPException(status_code=422, detail="invalid period") from exc
        raise
    return ClosePeriodResponse(
        batch_id=batch.id,
        txn_count=batch.operations_count,
        total_amount=batch.total_amount,
        total_qty=batch.total_qty,
    )


@router.post("/invoices/generate", response_model=InvoiceGenerateResponse)
def generate_invoice_endpoint(
    batch_id: str = Query(...),
    db: Session = Depends(get_db),
) -> InvoiceGenerateResponse:
    run_pdf_sync = os.getenv("DISABLE_CELERY", "0") == "1"
    try:
        invoice = generate_invoice_for_batch(db, batch_id=batch_id, run_pdf_sync=run_pdf_sync)
    except ValueError as exc:
        if str(exc) == "batch_not_found":
            raise HTTPException(status_code=404, detail="batch not found") from exc
        raise

    return InvoiceGenerateResponse(
        invoice_id=invoice.id,
        state=invoice.status.value,
        pdf_url=invoice.pdf_url,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice_endpoint(invoice_id: str, db: Session = Depends(get_db)) -> InvoiceOut:
    invoice = db.query(Invoice).filter_by(id=invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    return InvoiceOut(
        id=invoice.id,
        batch_id=invoice.clearing_batch_id,
        number=invoice.number or invoice.external_number,
        amount=invoice.total_amount,
        vat=invoice.tax_amount,
        state=invoice.status.value,
        pdf_url=invoice.pdf_url,
        pdf_object_key=invoice.pdf_object_key,
        issued_at=invoice.issued_at,
    )


__all__ = ["router"]
