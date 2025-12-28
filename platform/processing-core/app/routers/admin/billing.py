from datetime import date, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.models.billing_task_link import BillingTaskStatus, BillingTaskType
from app.models.contract_limits import TariffPlan, TariffPrice
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus
from app.schemas.billing import BillingSummaryPage
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.models.audit_log import AuditVisibility
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
    InvoiceTransitionRequest,
    InvoicePdfEnqueueResponse,
    InvoicePdfReadResponse,
    TariffPlanListResponse,
    TariffPlanRead,
    TariffPriceListResponse,
    TariffPricePayload,
    TariffPriceRead,
    BillingJobRunListResponse,
)
from app.schemas.reports import BillingSummaryItem
from app.schemas.settlement_allocations import SettlementSummaryItem, SettlementSummaryResponse
from app.models.billing_summary import BillingSummary
from app.models.operation import ProductType
from app.models.billing_period import BillingPeriod, BillingPeriodType
from app.services.reports_billing import finalize_billing_summary
from app.services.billing_run import BillingPeriodClosedError, BillingRunInProgress, BillingRunService, BillingRunValidationError
from app.services.billing_periods import BillingPeriodConflict, BillingPeriodService
from app.services.policy import PolicyAccessDenied
from app.services.reconciliation import BillingReconciliationService
from app.services.operations_scenarios.adjustments import AdjustmentService
from app.models.financial_adjustment import FinancialAdjustmentKind, FinancialAdjustmentStatus, RelatedEntityType
from app.models.operation import Operation
from app.models.billing_period import BillingPeriodStatus
from app.services.billing_job_runs import BillingJobRunService
from app.services.billing_task_links import BillingTaskLinkService
from app.services.billing_service import (
    generate_invoices_for_period,
    get_billing_summaries,
)
from app.services.billing import finalize_billing_day, run_billing_daily
from app.services.invoicing import run_invoice_monthly
from app.services.invoice_pdf import InvoicePdfService
from app.services.invoice_state_machine import InvoiceInvariantError, InvoiceStateMachine, InvalidTransitionError
from app.api.dependencies.admin import require_admin_user
from app.services.s3_storage import S3Storage
from app.repositories.billing_repository import BillingRepository
from app.services.job_locks import advisory_lock, make_lock_token, make_stable_key
from app.services.demo_seed import DemoSeeder
from app.services.settlement_allocations import list_settlement_summary
from app.services.legal_graph import (
    LegalGraphRegistry,
    LegalGraphSnapshotService,
    check_billing_period_completeness,
)
from app.models.legal_graph import LegalGraphSnapshotScopeType, LegalNodeType
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["admin"])


@router.get("/settlement-summary", response_model=SettlementSummaryResponse)
def admin_settlement_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    client_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> SettlementSummaryResponse:
    rows = list_settlement_summary(db, date_from=date_from, date_to=date_to, client_id=client_id)
    items = [
        SettlementSummaryItem(
            settlement_period_id=row.settlement_period_id,
            period_start=row.period_start,
            period_end=row.period_end,
            currency=row.currency,
            total_payments=row.total_payments,
            total_credits=row.total_credits,
            total_refunds=row.total_refunds,
            total_net=row.total_payments - row.total_credits - row.total_refunds,
            allocations_count=row.allocations_count,
        )
        for row in rows
    ]
    return SettlementSummaryResponse(items=items, total=len(items))


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
def admin_lock_billing_period(
    body: BillingPeriodPayload,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> BillingPeriodRead:
    service = BillingPeriodService(db)
    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    tenant_id = int(token.get("tenant_id") or 0)
    period_preview = service.get_or_create(
        period_type=body.period_type,
        start_at=body.start_at,
        end_at=body.end_at,
        tz=body.tz,
    )
    completeness = check_billing_period_completeness(
        db,
        tenant_id=tenant_id,
        period_id=str(period_preview.id),
    )
    if not completeness.ok:
        AuditService(db).audit(
            event_type="LEGAL_GRAPH_COMPLETENESS_FAILED",
            entity_type="billing_period",
            entity_id=str(period_preview.id),
            action="LOCK_DENIED",
            visibility=AuditVisibility.INTERNAL,
            after={
                "missing_nodes": completeness.missing_nodes,
                "missing_edges": completeness.missing_edges,
                "blocking_reasons": completeness.blocking_reasons,
            },
            request_ctx=request_ctx,
        )
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="billing_period_incomplete")
    try:
        period = service.lock(
            period_type=body.period_type,
            start_at=body.start_at,
            end_at=body.end_at,
            tz=body.tz,
            token=token,
        )
        LegalGraphRegistry(db, request_ctx=request_ctx).get_or_create_node(
            tenant_id=tenant_id,
            node_type=LegalNodeType.BILLING_PERIOD,
            ref_id=str(period.id),
            ref_table="billing_periods",
        )
        LegalGraphSnapshotService(db, request_ctx=request_ctx).create_snapshot(
            tenant_id=tenant_id,
            scope_type=LegalGraphSnapshotScopeType.BILLING_PERIOD,
            scope_ref_id=str(period.id),
            depth=3,
            actor_ctx=request_ctx,
        )
        db.commit()
    except PolicyAccessDenied as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BillingPeriodConflict as exc:
        AuditService(db).audit(
            event_type="BILLING_PERIOD_LOCK_CONFLICT",
            entity_type="billing_period",
            entity_id=None,
            action="LOCK_DENIED",
            reason=str(exc),
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    AuditService(db).audit(
        event_type="BILLING_PERIOD_LOCKED",
        entity_type="billing_period",
        entity_id=str(period.id),
        action="LOCK",
        after={
            "status": period.status.value if period.status else None,
            "locked_at": period.locked_at,
        },
        request_ctx=request_ctx,
    )
    return BillingPeriodRead.model_validate(period)


@router.post("/periods/finalize", response_model=BillingPeriodRead)
def admin_finalize_billing_period(
    body: BillingPeriodPayload,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> BillingPeriodRead:
    service = BillingPeriodService(db)
    try:
        period = service.finalize(
            period_type=body.period_type,
            start_at=body.start_at,
            end_at=body.end_at,
            tz=body.tz,
            token=token,
        )
        db.commit()
    except PolicyAccessDenied as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BillingPeriodConflict as exc:
        AuditService(db).audit(
            event_type="BILLING_PERIOD_FINALIZE_CONFLICT",
            entity_type="billing_period",
            entity_id=None,
            action="FINALIZE_DENIED",
            reason=str(exc),
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    AuditService(db).audit(
        event_type="BILLING_PERIOD_FINALIZED",
        entity_type="billing_period",
        entity_id=str(period.id),
        action="FINALIZE",
        after={
            "status": period.status.value if period.status else None,
            "finalized_at": period.finalized_at,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
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


@router.post("/seed")
def admin_seed_billing(idempotency_key: str | None = Query(None), db: Session = Depends(get_db)):
    seeder = DemoSeeder(db)
    scope_key = make_stable_key("billing_seed", {"seed": "demo"}, idempotency_key)
    job_service = BillingJobRunService(db)
    existing = job_service.find_by_correlation(BillingJobType.BILLING_SEED, scope_key)
    if existing and isinstance(existing.result_ref, dict):
        return existing.result_ref

    lock_token = make_lock_token("billing_seed", scope_key)
    with advisory_lock(db, lock_token) as acquired:
        if not acquired:
            raise HTTPException(status_code=409, detail="already running")

        job_run = job_service.start(
            BillingJobType.BILLING_SEED,
            params={"demo": True},
            correlation_id=scope_key,
        )
        result = seeder.seed()
        job_service.succeed(job_run, metrics={"billing_period_id": result.get("billing_period_id")}, result_ref=result)
        return result


@router.post("/run", response_model=BillingRunResponse)
def admin_run_billing(
    body: BillingRunRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> BillingRunResponse:
    service = BillingRunService(db)
    scope_key = make_stable_key(
        "billing_manual_run",
        {
            "period_type": body.period_type.value if hasattr(body.period_type, "value") else str(body.period_type),
            "start_at": body.start_at.isoformat(),
            "end_at": body.end_at.isoformat(),
            "tz": body.tz,
            "client_id": body.client_id or "*",
        },
        body.idempotency_key,
    )
    try:
        result = service.run(
            period_type=body.period_type,
            start_at=body.start_at,
            end_at=body.end_at,
            tz=body.tz,
            client_id=body.client_id,
            idempotency_key=scope_key,
            token=token,
        )
    except PolicyAccessDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BillingRunValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except BillingPeriodClosedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except BillingRunInProgress as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already running") from exc

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
    except BillingPeriodConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BillingSummaryItem.model_validate(summary)


@router.post("/run-daily")
def admin_run_billing_daily(
    billing_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        summaries = run_billing_daily(billing_date, session=db)
    except BillingPeriodConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    try:
        invoices = generate_invoices_for_period(
            db,
            period_from=body.period_from,
            period_to=body.period_to,
            status=body.status,
        )
    except BillingPeriodConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return InvoiceGenerateResponse(created_ids=[invoice.id for invoice in invoices])


@router.post("/invoices/{invoice_id}/status", response_model=InvoiceRead)
def admin_update_invoice_status(
    invoice_id: str,
    body: InvoiceStatusChangeRequest,
    db: Session = Depends(get_db),
) -> InvoiceRead:
    query = db.query(Invoice).filter(Invoice.id == invoice_id)
    if getattr(getattr(db.bind, "dialect", None), "name", None) == "postgresql":
        query = query.with_for_update()
    invoice = query.one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    machine = InvoiceStateMachine(invoice, db=db)
    try:
        machine.transition(
            to=body.status,
            actor="admin_api",
            reason=body.reason or "manual_status_update",
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceInvariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return InvoiceRead.model_validate(invoice, from_attributes=True)


@router.post("/invoices/{invoice_id}/transition", response_model=InvoiceRead)
def admin_transition_invoice(
    invoice_id: str,
    body: InvoiceTransitionRequest,
    db: Session = Depends(get_db),
) -> InvoiceRead:
    query = db.query(Invoice).filter(Invoice.id == invoice_id)
    if getattr(getattr(db.bind, "dialect", None), "name", None) == "postgresql":
        query = query.with_for_update()
    invoice = query.one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    machine = InvoiceStateMachine(invoice, db=db)
    try:
        machine.transition(
            to=body.to,
            actor="admin",
            reason=body.reason,
            payment_amount=body.payment_amount,
            credit_note_amount=body.credit_note_amount,
            metadata=body.metadata,
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceInvariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return InvoiceRead.model_validate(invoice, from_attributes=True)


@router.post("/invoices/run-monthly")
def admin_run_monthly_invoices(month: str | None = Query(None), db: Session = Depends(get_db)):
    if month:
        try:
            date.fromisoformat(f"{month}-01")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid month format, expected YYYY-MM") from exc

    try:
        from app.tasks.billing_pdf import run_monthly_invoices_task
    except Exception as exc:
        raise HTTPException(status_code=503, detail="celery_not_available") from exc

    correlation_id = str(uuid4())
    job_service = BillingJobRunService(db)
    params = {"month": month} if month else None
    job_run = job_service.start(
        BillingJobType.INVOICE_MONTHLY,
        params=params,
        correlation_id=correlation_id,
    )
    db.add(job_run)
    db.commit()

    async_result = run_monthly_invoices_task.delay(month, job_run_id=str(job_run.id), correlation_id=correlation_id)
    job_run.celery_task_id = async_result.id
    job_run.attempts = (job_run.attempts or 0) + 1
    db.add(job_run)

    link_service = BillingTaskLinkService(db)
    link_service.upsert(
        task_id=async_result.id,
        task_name="billing.generate_monthly_invoices",
        job_run_id=str(job_run.id),
        task_type=BillingTaskType.MONTHLY_RUN,
        status=BillingTaskStatus.QUEUED,
    )
    db.commit()

    return {"task_id": async_result.id, "job_run_id": str(job_run.id), "status": "QUEUED"}


@router.post("/invoices/{invoice_id}/pdf", response_model=InvoicePdfEnqueueResponse)
def admin_enqueue_invoice_pdf(
    invoice_id: str,
    force: bool = Query(False),
    idempotency_key: str | None = Query(None),
    db: Session = Depends(get_db),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    try:
        from app.tasks.billing_pdf import generate_invoice_pdf
    except Exception as exc:
        raise HTTPException(status_code=503, detail="celery_not_available") from exc

    job_service = BillingJobRunService(db)
    link_service = BillingTaskLinkService(db)
    scope_key = make_stable_key("invoice_pdf", {"invoice_id": invoice_id, "force": force}, idempotency_key)
    existing = job_service.find_by_correlation(BillingJobType.PDF_GENERATE, scope_key)
    if existing:
        if existing.status == BillingJobStatus.STARTED:
            return InvoicePdfEnqueueResponse(
                task_id=existing.celery_task_id or "",
                job_run_id=str(existing.id),
                pdf_status=invoice.pdf_status,
            )
        if existing.status == BillingJobStatus.SUCCESS:
            return InvoicePdfEnqueueResponse(
                task_id=existing.celery_task_id or "",
                job_run_id=str(existing.id),
                pdf_status=invoice.pdf_status,
            )

    correlation_id = scope_key

    lock_token = make_lock_token("invoice_pdf", scope_key)
    with advisory_lock(db, lock_token) as acquired:
        if not acquired:
            raise HTTPException(status_code=409, detail="already running")

        job_run = job_service.start(
            BillingJobType.PDF_GENERATE,
            params={"invoice_id": invoice_id, "force": force},
            correlation_id=correlation_id,
            invoice_id=invoice_id,
            billing_period_id=str(invoice.billing_period_id) if invoice.billing_period_id else None,
        )
        invoice.pdf_status = InvoicePdfStatus.QUEUED
        invoice.pdf_error = None
        db.add(invoice)
        db.flush()

        async_result = generate_invoice_pdf.delay(
            invoice.id,
            correlation_id=correlation_id,
            force=force,
            job_run_id=str(job_run.id),
        )
        job_run.celery_task_id = async_result.id
        job_run.attempts = (job_run.attempts or 0) + 1
        db.add(job_run)

        link_service.upsert(
            task_id=async_result.id,
            task_name="billing.generate_invoice_pdf",
            job_run_id=str(job_run.id),
            task_type=BillingTaskType.PDF_GENERATE,
            invoice_id=invoice.id,
            billing_period_id=str(invoice.billing_period_id) if invoice.billing_period_id else None,
            status=BillingTaskStatus.QUEUED,
        )
        db.commit()
        return InvoicePdfEnqueueResponse(task_id=async_result.id, job_run_id=str(job_run.id), pdf_status=invoice.pdf_status)


@router.get("/invoices/{invoice_id}/pdf", response_model=InvoicePdfReadResponse)
def admin_get_invoice_pdf(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")

    download_url = None
    if invoice.pdf_url:
        try:
            storage = S3Storage()
            prefix = f"s3://{storage.bucket}/"
            if invoice.pdf_url.startswith(prefix):
                key = invoice.pdf_url.replace(prefix, "", 1)
                download_url = storage.presign(key)
        except RuntimeError:
            download_url = None

    return InvoicePdfReadResponse(
        invoice_id=invoice.id,
        pdf_status=invoice.pdf_status,
        pdf_url=invoice.pdf_url,
        pdf_hash=invoice.pdf_hash,
        pdf_version=invoice.pdf_version,
        pdf_error=invoice.pdf_error,
        pdf_generated_at=invoice.pdf_generated_at,
        download_url=download_url,
    )


@router.get("/jobs", response_model=BillingJobRunListResponse)
def admin_list_billing_jobs(
    job_type: BillingJobType | None = Query(None),
    status: BillingJobStatus | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    invoice_id: str | None = Query(None),
    billing_period_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> BillingJobRunListResponse:
    query = db.query(BillingJobRun)
    if job_type:
        query = query.filter(BillingJobRun.job_type == job_type)
    if status:
        query = query.filter(BillingJobRun.status == status)
    if date_from:
        query = query.filter(BillingJobRun.started_at >= date_from)
    if date_to:
        query = query.filter(BillingJobRun.started_at <= date_to)
    if invoice_id:
        query = query.filter(BillingJobRun.invoice_id == invoice_id)
    if billing_period_id:
        query = query.filter(BillingJobRun.billing_period_id == billing_period_id)

    total = query.count()
    items = query.order_by(BillingJobRun.started_at.desc()).offset(offset).limit(limit).all()
    return BillingJobRunListResponse(items=items, total=total, limit=limit, offset=offset)
