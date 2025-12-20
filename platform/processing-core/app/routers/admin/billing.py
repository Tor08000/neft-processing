from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.contract_limits import TariffPlan, TariffPrice
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.billing import BillingSummaryPage
from app.schemas.admin.billing import (
    BillingAdjustmentRequest,
    BillingAdjustmentResponse,
    BillingPeriodFilter,
    BillingPeriodPayload,
    BillingPeriodRead,
    BillingPeriodListResponse,
    BillingReconcileRequest,
    BillingReconciliationRunResponse,
    BillingRunRequest,
    BillingRunResponse,
    InvoiceGenerateRequest,
    InvoiceGenerateResponse,
    InvoiceListResponse,
    InvoiceRead,
    InvoiceStatusChangeRequest,
    TariffPlanListResponse,
    TariffPlanRead,
    TariffPriceListResponse,
    TariffPricePayload,
    TariffPriceRead,
)
from app.schemas.reports import BillingSummaryItem
from app.models.billing_summary import BillingSummary
from app.models.operation import ProductType
from app.models.billing_period import BillingPeriod, BillingPeriodType
from app.services.reports_billing import finalize_billing_summary
from app.services.billing_run import BillingPeriodClosedError, BillingRunService, BillingRunValidationError
from app.services.billing_periods import BillingPeriodConflict, BillingPeriodService
from app.services.reconciliation import BillingReconciliationService
from app.services.operations_scenarios.adjustments import AdjustmentService
from app.models.financial_adjustment import FinancialAdjustmentKind, FinancialAdjustmentStatus, RelatedEntityType
from app.models.operation import Operation
from app.models.billing_period import BillingPeriodStatus
from app.services.billing_service import (
    generate_invoices_for_period,
    get_billing_summaries,
)
from app.services.billing import finalize_billing_day, run_billing_daily
from app.services.invoicing import run_invoice_monthly
from app.repositories.billing_repository import BillingRepository

router = APIRouter(prefix="/billing", tags=["admin"])


@router.get("/periods", response_model=BillingPeriodListResponse)
def admin_list_billing_periods(
    status: BillingPeriodStatus | None = Query(None),
    period_type: BillingPeriodType | None = Query(None),
    start_from: datetime | None = Query(None),
    start_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
) -> BillingPeriodListResponse:
    service = BillingPeriodService(db)
    items = service.list_periods(status=status, period_type=period_type, start_from=start_from, start_to=start_to)
    return BillingPeriodListResponse(items=items, total=len(items))


@router.post("/periods/lock", response_model=BillingPeriodRead)
def admin_lock_billing_period(body: BillingPeriodPayload, db: Session = Depends(get_db)) -> BillingPeriodRead:
    service = BillingPeriodService(db)
    try:
        period = service.lock(
            period_type=body.period_type,
            start_at=body.start_at,
            end_at=body.end_at,
            tz=body.tz,
        )
        db.commit()
    except BillingPeriodConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BillingPeriodRead.model_validate(period)


@router.post("/periods/finalize", response_model=BillingPeriodRead)
def admin_finalize_billing_period(body: BillingPeriodPayload, db: Session = Depends(get_db)) -> BillingPeriodRead:
    service = BillingPeriodService(db)
    try:
        period = service.finalize(
            period_type=body.period_type,
            start_at=body.start_at,
            end_at=body.end_at,
            tz=body.tz,
        )
        db.commit()
    except BillingPeriodConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BillingPeriodRead.model_validate(period)


@router.post("/reconcile", response_model=BillingReconciliationRunResponse)
def admin_reconcile_billing(body: BillingReconcileRequest, db: Session = Depends(get_db)) -> BillingReconciliationRunResponse:
    service = BillingReconciliationService(db)
    try:
        run = service.run(body.billing_period_id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BillingReconciliationRunResponse(
        run_id=str(run.id),
        status=run.status,
        total_invoices=run.total_invoices,
        ok_count=run.ok_count,
        mismatch_count=run.mismatch_count,
        missing_ledger_count=run.missing_ledger_count,
    )


@router.post("/adjustments", response_model=BillingAdjustmentResponse, status_code=status.HTTP_201_CREATED)
def admin_create_adjustment(body: BillingAdjustmentRequest, db: Session = Depends(get_db)) -> BillingAdjustmentResponse:
    period = db.query(BillingPeriod).filter(BillingPeriod.id == body.billing_period_id).one_or_none()
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="billing period not found")
    if period.status not in (BillingPeriodStatus.LOCKED, BillingPeriodStatus.FINALIZED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="billing period is not locked")

    operation = db.query(Operation).filter(Operation.id == body.operation_id).one_or_none()
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="operation not found")

    if body.kind not in (FinancialAdjustmentKind.CREDIT, FinancialAdjustmentKind.DEBIT):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported adjustment kind for billing")

    service = AdjustmentService(db)
    adjustment = service.ensure_adjustment(
        idempotency_key=body.idempotency_key,
        kind=body.kind,
        related_entity_type=RelatedEntityType.BILLING_PERIOD,
        related_entity_id=period.id,
        operation_id=operation.id,
        amount=body.amount,
        currency=body.currency,
        effective_date=body.effective_date,
    )
    db.commit()
    db.refresh(adjustment)
    return BillingAdjustmentResponse(
        id=str(adjustment.id),
        status=adjustment.status,
        operation_id=str(adjustment.operation_id),
        billing_period_id=str(period.id),
        amount=adjustment.amount,
        currency=adjustment.currency,
        effective_date=adjustment.effective_date,
    )


@router.post("/run", response_model=BillingRunResponse)
def admin_run_billing(body: BillingRunRequest, db: Session = Depends(get_db)) -> BillingRunResponse:
    service = BillingRunService(db)
    try:
        result = service.run(
            period_type=body.period_type,
            start_at=body.start_at,
            end_at=body.end_at,
            tz=body.tz,
            client_id=body.client_id,
        )
    except BillingRunValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except BillingPeriodClosedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return BillingRunResponse(
        billing_period_id=str(result.billing_period.id),
        period_from=result.period_from,
        period_to=result.period_to,
        clients_processed=result.clients_processed,
        invoices_created=result.invoices_created,
        invoices_rebuilt=result.invoices_rebuilt,
        invoices_skipped=result.invoices_skipped,
        invoice_lines_created=result.invoice_lines_created,
        total_amount=result.total_amount,
    )


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


@router.post("/run-daily")
def admin_run_billing_daily(
    billing_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    summaries = run_billing_daily(billing_date, session=db)
    resolved_date = billing_date or (summaries[0].billing_date if summaries else None)
    return {"processed": len(summaries), "billing_date": str(resolved_date) if resolved_date else None}


@router.post("/finalize-day")
def admin_finalize_billing_day(
    billing_date: date = Query(...),
    db: Session = Depends(get_db),
):
    updated = finalize_billing_day(billing_date, session=db)
    return {"updated": updated, "billing_date": str(billing_date)}


# -------------------------
# Tariffs
# -------------------------


@router.get("/tariffs", response_model=TariffPlanListResponse)
def admin_list_tariffs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> TariffPlanListResponse:
    query = db.query(TariffPlan)
    total = query.count()
    items = query.order_by(TariffPlan.created_at.desc()).offset(offset).limit(limit).all()
    return TariffPlanListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/tariffs/{tariff_id}", response_model=TariffPlanRead)
def admin_get_tariff(tariff_id: str, db: Session = Depends(get_db)) -> TariffPlanRead:
    tariff = db.query(TariffPlan).filter(TariffPlan.id == tariff_id).first()
    if tariff is None:
        raise HTTPException(status_code=404, detail="tariff not found")
    return tariff


def _get_tariff_or_404(db: Session, tariff_id: str) -> TariffPlan:
    tariff = db.query(TariffPlan).filter(TariffPlan.id == tariff_id).first()
    if tariff is None:
        raise HTTPException(status_code=404, detail="tariff not found")
    return tariff


@router.post("/tariffs/{tariff_id}/prices", response_model=TariffPriceRead, status_code=status.HTTP_200_OK)
def admin_create_or_update_tariff_price(
    tariff_id: str, body: TariffPricePayload, db: Session = Depends(get_db)
) -> TariffPriceRead:
    _get_tariff_or_404(db, tariff_id)

    if body.id is not None:
        price = db.query(TariffPrice).filter(TariffPrice.id == body.id, TariffPrice.tariff_id == tariff_id).first()
        if price is None:
            raise HTTPException(status_code=404, detail="tariff price not found")
        for field, value in body.model_dump(exclude={"id"}).items():
            setattr(price, field, value)
    else:
        price = TariffPrice(tariff_id=tariff_id, **body.model_dump(exclude={"id"}))
        db.add(price)

    db.commit()
    db.refresh(price)
    return price


@router.get("/tariffs/{tariff_id}/prices", response_model=TariffPriceListResponse)
def admin_list_tariff_prices(tariff_id: str, db: Session = Depends(get_db)) -> TariffPriceListResponse:
    _get_tariff_or_404(db, tariff_id)
    prices = (
        db.query(TariffPrice)
        .filter(TariffPrice.tariff_id == tariff_id)
        .order_by(TariffPrice.priority.asc(), TariffPrice.created_at.desc())
        .all()
    )
    return TariffPriceListResponse(items=prices)


# -------------------------
# Invoices
# -------------------------


@router.get("/invoices", response_model=InvoiceListResponse)
def admin_list_invoices(
    client_id: str | None = None,
    period_from: date | None = None,
    period_to: date | None = None,
    status: InvoiceStatus | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> InvoiceListResponse:
    query = db.query(Invoice)
    if client_id:
        query = query.filter(Invoice.client_id == client_id)
    if period_from:
        query = query.filter(Invoice.period_from >= period_from)
    if period_to:
        query = query.filter(Invoice.period_to <= period_to)
    if status:
        query = query.filter(Invoice.status == status)

    total = query.count()
    items = query.order_by(Invoice.created_at.desc()).offset(offset).limit(limit).all()
    serialized = [InvoiceRead.model_validate(invoice, from_attributes=True) for invoice in items]
    return InvoiceListResponse(items=serialized, total=total, limit=limit, offset=offset)


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def admin_get_invoice(invoice_id: str, db: Session = Depends(get_db)) -> InvoiceRead:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    return InvoiceRead.model_validate(invoice, from_attributes=True)


@router.post("/invoices/generate", response_model=InvoiceGenerateResponse, status_code=status.HTTP_202_ACCEPTED)
def admin_generate_invoices(body: InvoiceGenerateRequest, db: Session = Depends(get_db)) -> InvoiceGenerateResponse:
    invoices = generate_invoices_for_period(
        db,
        period_from=body.period_from,
        period_to=body.period_to,
        status=body.status,
    )
    return InvoiceGenerateResponse(created_ids=[invoice.id for invoice in invoices])


@router.post("/invoices/{invoice_id}/status", response_model=InvoiceRead)
def admin_update_invoice_status(
    invoice_id: str,
    body: InvoiceStatusChangeRequest,
    db: Session = Depends(get_db),
) -> InvoiceRead:
    repo = BillingRepository(db)
    updated = repo.update_status(invoice_id, body.status)
    if updated is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    return InvoiceRead.model_validate(updated, from_attributes=True)


@router.post("/invoices/run-monthly")
def admin_run_monthly_invoices(month: str | None = Query(None), db: Session = Depends(get_db)):
    try:
        target_month = date.fromisoformat(f"{month}-01") if month else None
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid month format, expected YYYY-MM")
    invoices = run_invoice_monthly(target_month, session=db)
    return {"created": [invoice.id for invoice in invoices], "count": len(invoices)}
