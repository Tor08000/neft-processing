from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.admin_rbac import require_any_admin_roles
from app.db import get_db
from app.models.audit_log import AuditLog, AuditVisibility
from app.models.finance import CreditNoteStatus, PaymentStatus
from app.models.partner_finance import (
    PartnerLedgerDirection,
    PartnerLedgerEntryType,
    PartnerPayoutPolicy,
    PartnerPayoutRequest,
    PartnerPayoutRequestStatus,
    PartnerPayoutSchedule,
)
from app.models.partner_legal import PartnerLegalProfile
from app.models.settlement_v1 import SettlementPeriod
from app.models.reconciliation import ReconciliationDiscrepancy, ReconciliationDiscrepancyStatus
from app.schemas.admin.finance import (
    AdminInvoiceActionResponse,
    AdminInvoiceDetail,
    AdminInvoiceListResponse,
    AdminInvoiceSummary,
    AdminPaymentIntakeActionResponse,
    AdminPaymentIntakeDetail,
    AdminPaymentIntakeListResponse,
    CreditNoteRequest,
    CreditNoteResponse,
    FinanceOverviewBlockedReason,
    FinanceOverviewResponse,
    PartnerLedgerSeedRequest,
    PartnerLedgerSeedResponse,
    PartnerPayoutPolicyUpsertRequest,
    PaymentRequest,
    PaymentResponse,
    PayoutActionResponse,
    PayoutDetail,
    PayoutPolicyInfo,
    PayoutQueueItem,
    PayoutQueueListResponse,
    PayoutTraceItem,
    WriteActionRequest,
)
from app.schemas.billing_payment_intakes import BillingPaymentIntakeStatus
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.billing_payment_intakes import get_invoice, get_payment_intake, list_payment_intakes, review_payment_intake
from app.services.client_notifications import ClientNotificationSeverity, create_notification, resolve_client_email
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.finance import (
    FinanceOperationInProgress,
    FinanceService,
    InvoiceNotFound,
    PaymentIdempotencyConflict,
)
from app.services.mor_metrics import metrics as mor_metrics
from app.services.partner_finance_service import PartnerFinanceService
from app.services.policy import PolicyAccessDenied
from app.services.s3_storage import S3Storage
from app.services.subscription_billing import update_invoice_status
from app.services.invoice_state_machine import InvalidTransitionError, InvoiceInvariantError
from app.services.job_locks import make_stable_key

router = APIRouter(prefix="/finance", tags=["admin"])

WRITE_ROLES = ["NEFT_FINANCE", "NEFT_SUPERADMIN", "NEFT_ADMIN", "ADMIN"]


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind())


def _tables_ready(db: Session, table_names: list[str]) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(db.get_bind())
        return all(inspector.has_table(name) for name in table_names)
    except Exception:
        return False


def _get_column(table: Table, name: str):
    return table.c[name] if name in table.c else None


def _correlation_id(request: Request | None) -> str | None:
    if not request:
        return None
    return request.headers.get("x-request-id") or request.headers.get("x-correlation-id")


def _write_error(request: Request, status_code: int, error: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": error, "request_id": _correlation_id(request)})


class SettlementSnapshotMissing(Exception):
    pass


def _serialize_invoice(row: dict) -> AdminInvoiceSummary:
    org_id = row.get("org_id") or row.get("client_id")
    period_start = row.get("period_start") or row.get("period_from")
    period_end = row.get("period_end") or row.get("period_to")
    total = row.get("total_amount") or row.get("amount_total") or row.get("amount")
    return AdminInvoiceSummary(
        id=str(row.get("id")),
        org_id=str(org_id) if org_id is not None else None,
        subscription_id=str(row.get("subscription_id")) if row.get("subscription_id") else None,
        status=str(row.get("status")),
        period_start=period_start,
        period_end=period_end,
        due_at=row.get("due_at"),
        paid_at=row.get("paid_at"),
        total=Decimal(str(total)) if total is not None else None,
        currency=row.get("currency"),
    )


def _serialize_invoice_detail(row: dict, pdf_url: str | None) -> AdminInvoiceDetail:
    base = _serialize_invoice(row)
    return AdminInvoiceDetail(**base.model_dump(), pdf_url=pdf_url)


def _serialize_payment_intake(row: dict, *, proof_url: str | None = None) -> AdminPaymentIntakeDetail:
    proof = None
    if row.get("proof_object_key"):
        proof = {
            "object_key": row.get("proof_object_key"),
            "file_name": row.get("proof_file_name"),
            "content_type": row.get("proof_content_type"),
            "size": row.get("proof_size"),
        }
    return AdminPaymentIntakeDetail(
        id=row["id"],
        org_id=row["org_id"],
        invoice_id=row["invoice_id"],
        status=row["status"],
        amount=row["amount"],
        currency=row["currency"],
        payer_name=row.get("payer_name"),
        payer_inn=row.get("payer_inn"),
        bank_reference=row.get("bank_reference"),
        paid_at_claimed=row.get("paid_at_claimed"),
        comment=row.get("comment"),
        proof=proof,
        proof_url=proof_url,
        created_by_user_id=row.get("created_by_user_id"),
        reviewed_by_admin=row.get("reviewed_by_admin"),
        reviewed_at=row.get("reviewed_at"),
        review_note=row.get("review_note"),
        created_at=row.get("created_at"),
        invoice_link=f"/finance/invoices/{row['invoice_id']}" if row.get("invoice_id") else None,
    )


def _payout_blockers(service: PartnerFinanceService, payout: PartnerPayoutRequest) -> list[str]:
    try:
        return service.evaluate_payout_blockers(
            partner_org_id=payout.partner_org_id,
            amount=Decimal(payout.amount),
            currency=payout.currency,
        )
    except Exception:
        return []


def _legal_status_by_partner(db: Session, partner_ids: list[str]) -> dict[str, str | None]:
    if not partner_ids:
        return {}
    profiles = (
        db.query(PartnerLegalProfile)
        .filter(PartnerLegalProfile.partner_id.in_(partner_ids))
        .all()
    )
    return {
        str(profile.partner_id): (
            profile.legal_status.value if hasattr(profile.legal_status, "value") else str(profile.legal_status)
        )
        for profile in profiles
    }


def _settlement_state_for_partner(db: Session, *, partner_id: str, currency: str) -> str | None:
    period = (
        db.query(SettlementPeriod)
        .filter(
            SettlementPeriod.partner_id == partner_id,
            SettlementPeriod.currency == currency,
        )
        .order_by(SettlementPeriod.period_end.desc())
        .first()
    )
    if not period:
        return None
    return period.status.value if hasattr(period.status, "value") else str(period.status)


def _correlation_chain_by_payout(db: Session, payout_ids: list[str]) -> dict[str, list[str]]:
    if not payout_ids:
        return {}
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "partner_payout_request",
            AuditLog.entity_id.in_(payout_ids),
        )
        .order_by(AuditLog.ts.asc())
        .all()
    )
    chains: dict[str, list[str]] = {payout_id: [] for payout_id in payout_ids}
    for item in logs:
        correlation_id = None
        if isinstance(item.external_refs, dict):
            correlation_id = item.external_refs.get("correlation_id")
        correlation_id = correlation_id or item.trace_id or item.request_id
        if not correlation_id:
            continue
        chain = chains.setdefault(item.entity_id, [])
        if correlation_id not in chain:
            chain.append(correlation_id)
    return chains


def _ensure_settlement_snapshot(db: Session, *, partner_id: str, currency: str) -> None:
    has_snapshot = (
        db.query(SettlementPeriod.id)
        .filter(
            SettlementPeriod.partner_id == partner_id,
            SettlementPeriod.currency == currency,
        )
        .order_by(SettlementPeriod.period_end.desc())
        .first()
        is not None
    )
    if not has_snapshot:
        raise SettlementSnapshotMissing("settlement_snapshot_missing")


def _serialize_payout(
    payout: PartnerPayoutRequest,
    blockers: list[str],
    policy: PartnerPayoutPolicy | None = None,
    trace: list[PayoutTraceItem] | None = None,
    legal_status: str | None = None,
    settlement_state: str | None = None,
    correlation_chain: list[str] | None = None,
) -> PayoutDetail:
    totals = {
        "gross": Decimal(payout.amount),
        "fee": Decimal("0"),
        "penalties": Decimal("0"),
        "net": Decimal(payout.amount),
    }
    policy_info = None
    if policy:
        policy_info = PayoutPolicyInfo(
            min_payout_amount=Decimal(policy.min_payout_amount or 0),
            payout_hold_days=int(policy.payout_hold_days or 0),
            payout_schedule=policy.payout_schedule.value if policy.payout_schedule else None,
        )
    return PayoutDetail(
        payout_id=str(payout.id),
        partner_org=str(payout.partner_org_id),
        amount=Decimal(payout.amount),
        currency=payout.currency,
        status=payout.status.value if hasattr(payout.status, "value") else str(payout.status),
        correlation_id=payout.correlation_id,
        blockers=blockers,
        block_reason=blockers[0] if blockers else None,
        legal_status=legal_status,
        settlement_state=settlement_state,
        correlation_chain=correlation_chain or [],
        created_at=payout.created_at,
        processed_at=payout.processed_at,
        policy=policy_info,
        trace=trace or [],
        totals=totals,
    )


@router.get("/overview", response_model=FinanceOverviewResponse)
def finance_overview(
    window: str = Query("24h", pattern="^(24h|7d)$"),
    db: Session = Depends(get_db),
) -> FinanceOverviewResponse:
    now = datetime.now(timezone.utc)
    window_delta = timedelta(days=7) if window == "7d" else timedelta(hours=24)
    since = now - window_delta

    overdue_orgs = 0
    overdue_amount = Decimal("0")
    invoices_issued = 0
    invoices_paid = 0
    payment_pending = 0
    reconciliation_unmatched = 0

    if _tables_ready(db, ["billing_invoices"]):
        invoices = _table(db, "billing_invoices")
        org_col = _get_column(invoices, "org_id") or _get_column(invoices, "client_id")
        status_col = _get_column(invoices, "status")
        due_col = _get_column(invoices, "due_at")
        issued_col = _get_column(invoices, "issued_at") or _get_column(invoices, "created_at")
        paid_col = _get_column(invoices, "paid_at")
        amount_col = _get_column(invoices, "amount_due") or _get_column(invoices, "amount_total") or _get_column(
            invoices,
            "total_amount",
        )

        if org_col is not None and status_col is not None:
            overdue_orgs = (
                db.execute(
                    select(func.count(func.distinct(org_col))).where(status_col == "OVERDUE")
                ).scalar()
                or 0
            )
        if amount_col is not None and status_col is not None:
            overdue_amount = Decimal(
                str(
                    db.execute(select(func.coalesce(func.sum(amount_col), 0)).where(status_col == "OVERDUE")).scalar()
                    or 0
                )
            )
        if issued_col is not None:
            invoices_issued = (
                db.execute(select(func.count()).where(issued_col >= since)).scalar() or 0
            )
        if paid_col is not None:
            invoices_paid = (
                db.execute(select(func.count()).where(paid_col >= since)).scalar() or 0
            )

    if _tables_ready(db, ["billing_payment_intakes"]):
        intakes = _table(db, "billing_payment_intakes")
        status_col = _get_column(intakes, "status")
        if status_col is not None:
            payment_pending = (
                db.execute(
                    select(func.count()).where(status_col.in_(["SUBMITTED", "UNDER_REVIEW"]))
                ).scalar()
                or 0
            )

    reconciliation_unmatched = (
        db.execute(
            select(func.count()).where(
                ReconciliationDiscrepancy.status == ReconciliationDiscrepancyStatus.OPEN,
                ReconciliationDiscrepancy.created_at >= since,
            )
        ).scalar()
        or 0
    )

    pending_payouts = db.query(PartnerPayoutRequest).filter(
        PartnerPayoutRequest.status == PartnerPayoutRequestStatus.REQUESTED
    )
    payout_queue_pending = pending_payouts.count()
    reason_counts: dict[str, int] = {}
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(None))
    for payout in pending_payouts.limit(200).all():
        for reason in _payout_blockers(service, payout):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    payout_blocked_top_reasons = [
        FinanceOverviewBlockedReason(reason=key, count=value)
        for key, value in sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    ]

    return FinanceOverviewResponse(
        window="7d" if window == "7d" else "24h",
        overdue_orgs=overdue_orgs,
        overdue_amount=overdue_amount,
        invoices_issued_24h=invoices_issued,
        invoices_paid_24h=invoices_paid,
        payment_intakes_pending=payment_pending,
        reconciliation_unmatched_24h=reconciliation_unmatched,
        payout_queue_pending=payout_queue_pending,
        payout_blocked_top_reasons=payout_blocked_top_reasons,
        mor_immutable_violations_24h=mor_metrics.settlement_immutable_violation_total,
        clawback_required_24h=mor_metrics.clawback_required_total,
    )


@router.get("/invoices", response_model=AdminInvoiceListResponse)
def list_invoices(
    status: str | None = Query(None),
    org_id: str | None = Query(None),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AdminInvoiceListResponse:
    if not _tables_ready(db, ["billing_invoices"]):
        return AdminInvoiceListResponse(items=[], total=0, limit=limit, offset=offset)

    invoices = _table(db, "billing_invoices")
    query = select(invoices)
    status_col = _get_column(invoices, "status")
    org_col = _get_column(invoices, "org_id") or _get_column(invoices, "client_id")
    period_start_col = _get_column(invoices, "period_start")
    period_end_col = _get_column(invoices, "period_end")
    issued_col = _get_column(invoices, "issued_at") or _get_column(invoices, "created_at")

    if status and status_col is not None:
        query = query.where(status_col == status)
    if org_id and org_col is not None:
        query = query.where(org_col == org_id)
    if date_from and period_start_col is not None:
        query = query.where(period_start_col >= date_from)
    elif date_from and issued_col is not None:
        query = query.where(issued_col >= datetime.combine(date_from, datetime.min.time()))
    if date_to and period_end_col is not None:
        query = query.where(period_end_col <= date_to)
    elif date_to and issued_col is not None:
        query = query.where(issued_col <= datetime.combine(date_to, datetime.max.time()))

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    order_col = _get_column(invoices, "created_at") or _get_column(invoices, "issued_at") or invoices.c.id
    rows = db.execute(query.order_by(order_col.desc()).offset(offset).limit(limit)).mappings().all()
    items = [_serialize_invoice(dict(row)) for row in rows]
    return AdminInvoiceListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/invoices/{invoice_id}", response_model=AdminInvoiceDetail)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
) -> AdminInvoiceDetail:
    if not _tables_ready(db, ["billing_invoices"]):
        raise HTTPException(status_code=404, detail="invoice_not_found")
    invoices = _table(db, "billing_invoices")
    row = db.execute(select(invoices).where(invoices.c.id == invoice_id)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="invoice_not_found")

    pdf_url = row.get("pdf_url")
    object_key = row.get("pdf_object_key")
    if object_key:
        pdf_url = S3Storage().presign_download(object_key=object_key, expires=3600)
    return _serialize_invoice_detail(dict(row), pdf_url)


@router.post("/invoices/{invoice_id}/mark-paid", response_model=AdminInvoiceActionResponse)
def mark_invoice_paid(
    invoice_id: str,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> AdminInvoiceActionResponse:
    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    invoice = update_invoice_status(db, invoice_id=invoice_id, status="PAID", request_ctx=request_ctx)
    if not invoice:
        raise _write_error(request, 404, "invoice_not_found")
    AuditService(db).audit(
        event_type="INVOICE_MARKED_PAID",
        entity_type="billing_invoice",
        entity_id=str(invoice_id),
        action="MARK_PAID",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        after={"status": "PAID"},
        request_ctx=request_ctx,
    )
    db.commit()
    detail = _serialize_invoice_detail(invoice, invoice.get("download_url") or invoice.get("pdf_url"))
    return AdminInvoiceActionResponse(invoice=detail, correlation_id=_correlation_id(request))


@router.post("/invoices/{invoice_id}/void", response_model=AdminInvoiceActionResponse)
def void_invoice(
    invoice_id: str,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> AdminInvoiceActionResponse:
    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    invoice = update_invoice_status(db, invoice_id=invoice_id, status="VOID", request_ctx=request_ctx)
    if not invoice:
        raise _write_error(request, 404, "invoice_not_found")
    AuditService(db).audit(
        event_type="INVOICE_VOIDED",
        entity_type="billing_invoice",
        entity_id=str(invoice_id),
        action="VOID",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        after={"status": "VOID"},
        request_ctx=request_ctx,
    )
    db.commit()
    detail = _serialize_invoice_detail(invoice, invoice.get("download_url") or invoice.get("pdf_url"))
    return AdminInvoiceActionResponse(invoice=detail, correlation_id=_correlation_id(request))


@router.post("/invoices/{invoice_id}/mark-overdue", response_model=AdminInvoiceActionResponse)
def mark_invoice_overdue(
    invoice_id: str,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> AdminInvoiceActionResponse:
    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    invoice = update_invoice_status(db, invoice_id=invoice_id, status="OVERDUE", request_ctx=request_ctx)
    if not invoice:
        raise _write_error(request, 404, "invoice_not_found")
    AuditService(db).audit(
        event_type="INVOICE_MARKED_OVERDUE",
        entity_type="billing_invoice",
        entity_id=str(invoice_id),
        action="MARK_OVERDUE",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        after={"status": "OVERDUE"},
        request_ctx=request_ctx,
    )
    db.commit()
    detail = _serialize_invoice_detail(invoice, invoice.get("download_url") or invoice.get("pdf_url"))
    return AdminInvoiceActionResponse(invoice=detail, correlation_id=_correlation_id(request))


@router.get("/payment-intakes", response_model=AdminPaymentIntakeListResponse)
def list_finance_payment_intakes(
    status: BillingPaymentIntakeStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AdminPaymentIntakeListResponse:
    rows, total = list_payment_intakes(db, status=status.value if status else None, limit=limit, offset=offset)
    storage = S3Storage()
    items = []
    for row in rows:
        proof_url = None
        if row.get("proof_object_key"):
            proof_url = storage.presign_download(object_key=row["proof_object_key"], expires=3600)
        items.append(_serialize_payment_intake(row, proof_url=proof_url))
    return AdminPaymentIntakeListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/payment-intakes/{intake_id}", response_model=AdminPaymentIntakeDetail)
def get_finance_payment_intake(
    intake_id: int,
    db: Session = Depends(get_db),
) -> AdminPaymentIntakeDetail:
    intake = get_payment_intake(db, intake_id=intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="payment_intake_not_found")
    storage = S3Storage()
    proof_url = None
    if intake.get("proof_object_key"):
        proof_url = storage.presign_download(object_key=intake["proof_object_key"], expires=3600)
    return _serialize_payment_intake(intake, proof_url=proof_url)


@router.post("/payment-intakes/{intake_id}/approve", response_model=AdminPaymentIntakeActionResponse)
def approve_finance_payment_intake(
    intake_id: int,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> AdminPaymentIntakeActionResponse:
    intake = get_payment_intake(db, intake_id=intake_id)
    if not intake:
        raise _write_error(request, 404, "payment_intake_not_found")
    if intake["status"] == BillingPaymentIntakeStatus.APPROVED.value:
        raise _write_error(request, 409, "already_approved")

    reviewed_by = str(token.get("user_id") or token.get("sub") or token.get("email") or "admin")
    updated = review_payment_intake(
        db,
        intake_id=intake_id,
        status=BillingPaymentIntakeStatus.APPROVED.value,
        reviewed_by_admin=reviewed_by,
        review_note=payload.reason,
    )
    if not updated:
        raise _write_error(request, 404, "payment_intake_not_found")

    invoice = get_invoice(db, invoice_id=intake["invoice_id"])
    if not invoice:
        raise _write_error(request, 404, "invoice_not_found")

    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    update_invoice_status(db, invoice_id=intake["invoice_id"], status="PAID", request_ctx=request_ctx)
    get_org_entitlements_snapshot(db, org_id=invoice["org_id"])

    AuditService(db).audit(
        event_type="PAYMENT_INTAKE_APPROVED",
        entity_type="billing_payment_intake",
        entity_id=str(intake_id),
        action="APPROVE",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        after={
            "org_id": intake["org_id"],
            "invoice_id": intake["invoice_id"],
            "amount": str(intake["amount"]),
            "currency": intake["currency"],
        },
        request_ctx=request_ctx,
    )

    client_email = resolve_client_email(db, str(intake["org_id"]))
    create_notification(
        db,
        org_id=str(intake["org_id"]),
        event_type="payment_intake_approved",
        severity=ClientNotificationSeverity.INFO,
        title="Оплата подтверждена",
        body=f"Оплата по счету №{intake['invoice_id']} подтверждена.",
        link=f"/finance/invoices/{intake['invoice_id']}",
        entity_type="billing_payment_intake",
        entity_id=str(intake_id),
        email_to=client_email,
        email_context={"invoice_id": str(intake["invoice_id"])},
    )
    db.commit()
    return AdminPaymentIntakeActionResponse(
        intake=_serialize_payment_intake(updated),
        correlation_id=_correlation_id(request),
    )


@router.post("/payment-intakes/{intake_id}/confirm", response_model=AdminPaymentIntakeActionResponse)
def confirm_finance_payment_intake(
    intake_id: int,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> AdminPaymentIntakeActionResponse:
    return approve_finance_payment_intake(
        intake_id=intake_id,
        payload=payload,
        request=request,
        token=token,
        db=db,
    )


@router.post("/payment-intakes/{intake_id}/reject", response_model=AdminPaymentIntakeActionResponse)
def reject_finance_payment_intake(
    intake_id: int,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> AdminPaymentIntakeActionResponse:
    intake = get_payment_intake(db, intake_id=intake_id)
    if not intake:
        raise _write_error(request, 404, "payment_intake_not_found")

    reviewed_by = str(token.get("user_id") or token.get("sub") or token.get("email") or "admin")
    updated = review_payment_intake(
        db,
        intake_id=intake_id,
        status=BillingPaymentIntakeStatus.REJECTED.value,
        reviewed_by_admin=reviewed_by,
        review_note=payload.reason,
    )
    if not updated:
        raise _write_error(request, 404, "payment_intake_not_found")

    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    AuditService(db).audit(
        event_type="PAYMENT_INTAKE_REJECTED",
        entity_type="billing_payment_intake",
        entity_id=str(intake_id),
        action="REJECT",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        after={
            "org_id": intake["org_id"],
            "invoice_id": intake["invoice_id"],
            "amount": str(intake["amount"]),
            "currency": intake["currency"],
        },
        request_ctx=request_ctx,
    )

    client_email = resolve_client_email(db, str(intake["org_id"]))
    create_notification(
        db,
        org_id=str(intake["org_id"]),
        event_type="payment_intake_rejected",
        severity=ClientNotificationSeverity.WARNING,
        title="Оплата отклонена",
        body=f"Оплата по счету №{intake['invoice_id']} отклонена.",
        link=f"/finance/invoices/{intake['invoice_id']}",
        entity_type="billing_payment_intake",
        entity_id=str(intake_id),
        email_to=client_email,
        email_context={"invoice_id": str(intake["invoice_id"])},
    )
    db.commit()
    return AdminPaymentIntakeActionResponse(
        intake=_serialize_payment_intake(updated),
        correlation_id=_correlation_id(request),
    )


@router.post("/partners/{partner_id}/payout-policy", response_model=PayoutPolicyInfo)
def upsert_partner_payout_policy(
    partner_id: str,
    payload: PartnerPayoutPolicyUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
) -> PayoutPolicyInfo:
    _ = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    policy = (
        db.query(PartnerPayoutPolicy)
        .filter(PartnerPayoutPolicy.partner_org_id == partner_id)
        .filter(PartnerPayoutPolicy.currency == payload.currency)
        .one_or_none()
    )
    if policy is None:
        policy = PartnerPayoutPolicy(partner_org_id=partner_id, currency=payload.currency)
        db.add(policy)
    policy.min_payout_amount = payload.min_payout_amount
    policy.payout_hold_days = payload.payout_hold_days
    try:
        policy.payout_schedule = PartnerPayoutSchedule(payload.payout_schedule)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_payout_schedule") from exc
    db.commit()
    return PayoutPolicyInfo(
        min_payout_amount=Decimal(policy.min_payout_amount),
        payout_hold_days=int(policy.payout_hold_days),
        payout_schedule=policy.payout_schedule.value if hasattr(policy.payout_schedule, "value") else str(policy.payout_schedule),
    )


@router.post("/partners/{partner_id}/ledger/seed", response_model=PartnerLedgerSeedResponse, status_code=201)
def seed_partner_ledger_entry(
    partner_id: str,
    payload: PartnerLedgerSeedRequest,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
) -> PartnerLedgerSeedResponse:
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)))
    try:
        entry_type = PartnerLedgerEntryType(payload.entry_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_entry_type") from exc
    try:
        direction = PartnerLedgerDirection(payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_direction") from exc
    entry = service.post_entry(
        partner_org_id=partner_id,
        entry_type=entry_type,
        amount=payload.amount,
        currency=payload.currency,
        direction=direction,
        meta_json={"description": payload.description} if payload.description else None,
    )
    db.commit()
    account = service.get_account(partner_org_id=partner_id, currency=payload.currency)
    return PartnerLedgerSeedResponse(
        entry_id=str(entry.id),
        partner_org_id=partner_id,
        balance_available=Decimal(account.balance_available or 0),
        currency=account.currency,
    )


@router.get("/payouts", response_model=PayoutQueueListResponse)
def list_payout_queue(
    status: str | None = Query(None),
    blocked: bool | None = Query(None),
    reason: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PayoutQueueListResponse:
    query = db.query(PartnerPayoutRequest)
    if status:
        query = query.filter(PartnerPayoutRequest.status == status)
    total = query.count()
    payouts = query.order_by(PartnerPayoutRequest.created_at.desc()).offset(offset).limit(limit).all()
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(None))
    payout_ids = [str(payout.id) for payout in payouts]
    partner_ids = [str(payout.partner_org_id) for payout in payouts]
    legal_statuses = _legal_status_by_partner(db, partner_ids)
    correlation_chains = _correlation_chain_by_payout(db, payout_ids)
    items = []
    for payout in payouts:
        blockers = _payout_blockers(service, payout)
        if blocked is True and not blockers:
            continue
        if blocked is False and blockers:
            continue
        if reason and reason not in blockers:
            continue
        settlement_state = _settlement_state_for_partner(
            db,
            partner_id=str(payout.partner_org_id),
            currency=payout.currency,
        )
        chain = correlation_chains.get(str(payout.id), [])
        if payout.correlation_id and payout.correlation_id not in chain:
            chain = [*chain, payout.correlation_id]
        items.append(
            PayoutQueueItem(
                payout_id=str(payout.id),
                partner_org=str(payout.partner_org_id),
                amount=Decimal(payout.amount),
                currency=payout.currency,
                status=payout.status.value if hasattr(payout.status, "value") else str(payout.status),
                correlation_id=payout.correlation_id,
                blockers=blockers,
                block_reason=blockers[0] if blockers else None,
                legal_status=legal_statuses.get(str(payout.partner_org_id)),
                settlement_state=settlement_state,
                correlation_chain=chain,
                created_at=payout.created_at,
            )
        )
    filtered_total = total
    if blocked is not None or reason:
        filtered_total = len(items)
    return PayoutQueueListResponse(items=items, total=filtered_total, limit=limit, offset=offset)


@router.get("/payouts/{payout_id}", response_model=PayoutDetail)
def get_payout_detail(
    payout_id: str,
    db: Session = Depends(get_db),
) -> PayoutDetail:
    payout = db.query(PartnerPayoutRequest).filter(PartnerPayoutRequest.id == payout_id).one_or_none()
    if not payout:
        raise HTTPException(status_code=404, detail="payout_not_found")
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(None))
    blockers = _payout_blockers(service, payout)
    policy = service.get_payout_policy(partner_org_id=payout.partner_org_id, currency=payout.currency)
    trace: list[PayoutTraceItem] = []
    settlement_state = _settlement_state_for_partner(
        db,
        partner_id=str(payout.partner_org_id),
        currency=payout.currency,
    )
    legal_status = _legal_status_by_partner(db, [str(payout.partner_org_id)]).get(str(payout.partner_org_id))
    correlation_chain = _correlation_chain_by_payout(db, [str(payout.id)]).get(str(payout.id), [])
    if payout.correlation_id and payout.correlation_id not in correlation_chain:
        correlation_chain = [*correlation_chain, payout.correlation_id]
    return _serialize_payout(
        payout,
        blockers,
        policy=policy,
        trace=trace,
        legal_status=legal_status,
        settlement_state=settlement_state,
        correlation_chain=correlation_chain,
    )


@router.post("/payouts/{payout_id}/approve", response_model=PayoutActionResponse)
def approve_payout(
    payout_id: str,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> PayoutActionResponse:
    payout = db.query(PartnerPayoutRequest).filter(PartnerPayoutRequest.id == payout_id).one_or_none()
    if not payout:
        raise _write_error(request, 404, "payout_not_found")
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)))
    previous_status = payout.status
    correlation_id = payload.correlation_id or payout.correlation_id
    try:
        _ensure_settlement_snapshot(db, partner_id=str(payout.partner_org_id), currency=payout.currency)
        service.approve_payout(payout=payout, approved_by=str(token.get("user_id") or token.get("sub") or "admin"))
        db.commit()
    except SettlementSnapshotMissing as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "error": str(exc),
                "reason_code": "SETTLEMENT_SNAPSHOT_MISSING",
                "request_id": _correlation_id(request),
            },
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise _write_error(request, 400, str(exc)) from exc
    AuditService(db).audit(
        event_type="PAYOUT_APPROVED",
        entity_type="partner_payout_request",
        entity_id=str(payout_id),
        action="APPROVE",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        before={"status": previous_status.value if hasattr(previous_status, "value") else str(previous_status)},
        after={"status": payout.status.value if hasattr(payout.status, "value") else str(payout.status)},
        external_refs={"correlation_id": correlation_id} if correlation_id else None,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    settlement_state = _settlement_state_for_partner(
        db,
        partner_id=str(payout.partner_org_id),
        currency=payout.currency,
    )
    legal_status = _legal_status_by_partner(db, [str(payout.partner_org_id)]).get(str(payout.partner_org_id))
    correlation_chain = _correlation_chain_by_payout(db, [str(payout.id)]).get(str(payout.id), [])
    if correlation_id and correlation_id not in correlation_chain:
        correlation_chain = [*correlation_chain, correlation_id]
    detail = _serialize_payout(
        payout,
        _payout_blockers(service, payout),
        legal_status=legal_status,
        settlement_state=settlement_state,
        correlation_chain=correlation_chain,
    )
    return PayoutActionResponse(payout=detail, correlation_id=correlation_id)


@router.post("/payouts/{payout_id}/reject", response_model=PayoutActionResponse)
def reject_payout(
    payout_id: str,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> PayoutActionResponse:
    payout = db.query(PartnerPayoutRequest).filter(PartnerPayoutRequest.id == payout_id).one_or_none()
    if not payout:
        raise _write_error(request, 404, "payout_not_found")
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)))
    previous_status = payout.status
    correlation_id = payload.correlation_id or payout.correlation_id
    try:
        service.reject_payout(
            payout=payout,
            approved_by=str(token.get("user_id") or token.get("sub") or "admin"),
            reason=payload.reason,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise _write_error(request, 400, str(exc)) from exc
    AuditService(db).audit(
        event_type="PAYOUT_REJECTED",
        entity_type="partner_payout_request",
        entity_id=str(payout_id),
        action="REJECT",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        before={"status": previous_status.value if hasattr(previous_status, "value") else str(previous_status)},
        after={"status": payout.status.value if hasattr(payout.status, "value") else str(payout.status)},
        external_refs={"correlation_id": correlation_id} if correlation_id else None,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    settlement_state = _settlement_state_for_partner(
        db,
        partner_id=str(payout.partner_org_id),
        currency=payout.currency,
    )
    legal_status = _legal_status_by_partner(db, [str(payout.partner_org_id)]).get(str(payout.partner_org_id))
    correlation_chain = _correlation_chain_by_payout(db, [str(payout.id)]).get(str(payout.id), [])
    if correlation_id and correlation_id not in correlation_chain:
        correlation_chain = [*correlation_chain, correlation_id]
    detail = _serialize_payout(
        payout,
        _payout_blockers(service, payout),
        legal_status=legal_status,
        settlement_state=settlement_state,
        correlation_chain=correlation_chain,
    )
    return PayoutActionResponse(payout=detail, correlation_id=correlation_id)


@router.post("/payouts/{payout_id}/mark-paid", response_model=PayoutActionResponse)
def mark_payout_paid(
    payout_id: str,
    payload: WriteActionRequest,
    request: Request,
    token: dict = Depends(require_any_admin_roles(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> PayoutActionResponse:
    payout = db.query(PartnerPayoutRequest).filter(PartnerPayoutRequest.id == payout_id).one_or_none()
    if not payout:
        raise _write_error(request, 404, "payout_not_found")
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)))
    previous_status = payout.status
    correlation_id = payload.correlation_id or payout.correlation_id
    try:
        _ensure_settlement_snapshot(db, partner_id=str(payout.partner_org_id), currency=payout.currency)
        service.mark_paid(payout=payout)
        db.commit()
    except SettlementSnapshotMissing as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "error": str(exc),
                "reason_code": "SETTLEMENT_SNAPSHOT_MISSING",
                "request_id": _correlation_id(request),
            },
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise _write_error(request, 400, str(exc)) from exc
    AuditService(db).audit(
        event_type="PAYOUT_MARKED_PAID",
        entity_type="partner_payout_request",
        entity_id=str(payout_id),
        action="MARK_PAID",
        visibility=AuditVisibility.INTERNAL,
        reason=payload.reason,
        before={"status": previous_status.value if hasattr(previous_status, "value") else str(previous_status)},
        after={"status": payout.status.value if hasattr(payout.status, "value") else str(payout.status)},
        external_refs={"correlation_id": correlation_id} if correlation_id else None,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    settlement_state = _settlement_state_for_partner(
        db,
        partner_id=str(payout.partner_org_id),
        currency=payout.currency,
    )
    legal_status = _legal_status_by_partner(db, [str(payout.partner_org_id)]).get(str(payout.partner_org_id))
    correlation_chain = _correlation_chain_by_payout(db, [str(payout.id)]).get(str(payout.id), [])
    if correlation_id and correlation_id not in correlation_chain:
        correlation_chain = [*correlation_chain, correlation_id]
    detail = _serialize_payout(
        payout,
        _payout_blockers(service, payout),
        legal_status=legal_status,
        settlement_state=settlement_state,
        correlation_chain=correlation_chain,
    )
    return PayoutActionResponse(payout=detail, correlation_id=correlation_id)


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    body: PaymentRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    service = FinanceService(db)
    scope_key = make_stable_key(
        "finance_payment",
        {"invoice_id": body.invoice_id, "amount": body.amount, "currency": body.currency},
        body.idempotency_key,
    )
    try:
        result = service.apply_payment(
            invoice_id=body.invoice_id,
            amount=body.amount,
            currency=body.currency,
            idempotency_key=scope_key,
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            token=token,
        )
    except PolicyAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvoiceNotFound as exc:
        raise HTTPException(status_code=404, detail="invoice not found") from exc
    except FinanceOperationInProgress as exc:
        raise HTTPException(status_code=409, detail="already running") from exc
    except PaymentIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        AuditService(db).audit(
            event_type="PAYMENT_CONFLICT",
            entity_type="invoice",
            entity_id=body.invoice_id,
            action="PAYMENT_DENIED",
            reason=str(exc),
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceInvariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    AuditService(db).audit(
        event_type="PAYMENT_POSTED",
        entity_type="payment",
        entity_id=str(result.payment.id),
        action="CREATE",
        after={
            "invoice_id": result.payment.invoice_id,
            "amount": result.payment.amount,
            "currency": result.payment.currency,
            "status": result.payment.status.value if result.payment.status else None,
            "invoice_status": result.invoice.status.value if result.invoice.status else None,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    return PaymentResponse(
        payment_id=str(result.payment.id),
        invoice_id=result.payment.invoice_id,
        amount=result.payment.amount,
        currency=result.payment.currency,
        due_amount=result.invoice.amount_due,
        invoice_status=result.invoice.status,
        status=result.payment.status or PaymentStatus.POSTED,
        created_at=result.payment.created_at,
    )


@router.post("/credit-notes", response_model=CreditNoteResponse, status_code=201)
def create_credit_note(
    body: CreditNoteRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> CreditNoteResponse:
    service = FinanceService(db)
    scope_key = make_stable_key(
        "finance_credit_note",
        {"invoice_id": body.invoice_id, "amount": body.amount, "currency": body.currency, "reason": body.reason or ""},
        body.idempotency_key,
    )
    try:
        result = service.create_credit_note(
            invoice_id=body.invoice_id,
            amount=body.amount,
            currency=body.currency,
            reason=body.reason,
            idempotency_key=scope_key,
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            token=token,
        )
    except PolicyAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvoiceNotFound as exc:
        raise HTTPException(status_code=404, detail="invoice not found") from exc
    except FinanceOperationInProgress as exc:
        raise HTTPException(status_code=409, detail="already running") from exc
    except InvalidTransitionError as exc:
        AuditService(db).audit(
            event_type="CREDIT_NOTE_CONFLICT",
            entity_type="invoice",
            entity_id=body.invoice_id,
            action="CREDIT_NOTE_DENIED",
            reason=str(exc),
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvoiceInvariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    AuditService(db).audit(
        event_type="CREDIT_NOTE_CREATED",
        entity_type="credit_note",
        entity_id=str(result.credit_note.id),
        action="CREATE",
        after={
            "invoice_id": result.credit_note.invoice_id,
            "amount": result.credit_note.amount,
            "currency": result.credit_note.currency,
            "status": result.credit_note.status.value if result.credit_note.status else None,
            "invoice_status": result.invoice.status.value if result.invoice.status else None,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    return CreditNoteResponse(
        credit_note_id=str(result.credit_note.id),
        invoice_id=result.credit_note.invoice_id,
        amount=result.credit_note.amount,
        currency=result.credit_note.currency,
        due_amount=result.invoice.amount_due,
        invoice_status=result.invoice.status,
        status=result.credit_note.status or CreditNoteStatus.POSTED,
        created_at=result.credit_note.created_at,
    )


__all__ = ["router"]
