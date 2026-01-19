from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.export_jobs import ExportJob, ExportJobReportType, ExportJobStatus
from app.models.marketplace_orders import MarketplaceOrder
from app.models.marketplace_settlement import MarketplaceSettlementSnapshot
from app.models.partner_finance import PartnerAct, PartnerInvoice, PartnerLedgerEntry, PartnerPayoutRequest
from app.models.payout_batch import PayoutBatch
from app.schemas.partner_finance import (
    PartnerBalanceOut,
    PartnerDocumentListResponse,
    PartnerDocumentOut,
    PartnerLedgerEntryOut,
    PartnerLedgerListResponse,
    PartnerPayoutListResponse,
    PartnerPayoutPreviewOut,
    PartnerPayoutRequestIn,
    PartnerPayoutRequestOut,
)
from app.schemas.partner_trust import (
    LedgerExplainOut,
    PartnerExportJobCreateResponse,
    PartnerExportJobListResponse,
    PartnerExportJobOut,
    PayoutTraceOut,
    PayoutTraceOrderOut,
    PayoutTraceSummaryOut,
    SettlementChainExportRequest,
)
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.audit_service import AuditService, AuditVisibility, _sanitize_token_for_audit, request_context_from_request
from app.models.partner_legal import PartnerLegalStatus
from app.services.partner_legal_service import PartnerLegalError, PartnerLegalService
from app.services.export_metrics import metrics as export_metrics
from app.services.partner_finance_service import (
    PartnerFinanceService,
    PartnerPayoutBlockedError,
    PartnerPayoutPolicyError,
)
from app.services.partner_trust_metrics import metrics as partner_trust_metrics
from app.services.reports_render import ExportRenderValidationError, normalize_filters
from app.services.s3_storage import S3Storage
from neft_shared.settings import get_settings

router = APIRouter(prefix="/partner", tags=["partner-finance"])
settings = get_settings()


def _resolve_org_id(principal: Principal) -> str:
    raw = principal.raw_claims.get("org_id") or principal.raw_claims.get("partner_id")
    if raw is None:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "missing_org_context"})
    return str(raw)


def _ensure_capability(db: Session, principal: Principal, capability: str) -> str:
    org_id_raw = _resolve_org_id(principal)
    try:
        org_id_int = int(org_id_raw)
    except (TypeError, ValueError):
        org_id_int = None
    if org_id_int is not None:
        snapshot = get_org_entitlements_snapshot(db, org_id=org_id_int)
        capabilities = snapshot.entitlements.get("capabilities") or []
        if capability not in capabilities:
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "reason": "missing_capability", "capability": capability},
            )
    return org_id_raw


def _export_job_to_out(job: ExportJob) -> PartnerExportJobOut:
    return PartnerExportJobOut(
        id=str(job.id),
        org_id=str(job.org_id),
        created_by_user_id=job.created_by_user_id,
        report_type=job.report_type.value if hasattr(job.report_type, "value") else str(job.report_type),
        format=job.format,
        status=job.status,
        filters=job.filters_json or {},
        file_name=job.file_name,
        content_type=job.content_type,
        row_count=job.row_count,
        processed_rows=job.processed_rows,
        progress_percent=job.progress_percent,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        expires_at=job.expires_at,
    )


def _resolve_user_id(principal: Principal) -> str:
    user_id = str(principal.user_id or principal.raw_claims.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user")
    return user_id


def _audit_forbidden_access(
    *,
    principal: Principal,
    request: Request,
    db: Session,
    entity_type: str,
    entity_id: str,
) -> None:
    AuditService(db).audit(
        event_type="PARTNER_ACCESS_FORBIDDEN",
        entity_type=entity_type,
        entity_id=entity_id,
        action="FORBIDDEN",
        visibility=AuditVisibility.INTERNAL,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(principal.raw_claims)),
    )


@router.get("/balance", response_model=PartnerBalanceOut)
def get_partner_balance(
    principal: Principal = Depends(require_permission("partner:finance:view")),
    db: Session = Depends(get_db),
) -> PartnerBalanceOut:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    account = PartnerFinanceService(db).get_account(partner_org_id=partner_org_id, currency="RUB")
    return PartnerBalanceOut(
        partner_org_id=str(account.org_id),
        currency=account.currency,
        balance_available=Decimal(account.balance_available or 0),
        balance_pending=Decimal(account.balance_pending or 0),
        balance_blocked=Decimal(account.balance_blocked or 0),
    )


@router.get("/ledger", response_model=PartnerLedgerListResponse)
def get_partner_ledger(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("partner:finance:view")),
    db: Session = Depends(get_db),
) -> PartnerLedgerListResponse:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    entries = (
        db.query(PartnerLedgerEntry)
        .filter(PartnerLedgerEntry.partner_org_id == partner_org_id)
        .order_by(PartnerLedgerEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PartnerLedgerListResponse(
        items=[
            PartnerLedgerEntryOut(
                id=str(entry.id),
                partner_org_id=str(entry.partner_org_id),
                order_id=str(entry.order_id) if entry.order_id else None,
                entry_type=entry.entry_type.value if hasattr(entry.entry_type, "value") else str(entry.entry_type),
                amount=Decimal(entry.amount),
                currency=entry.currency,
                direction=entry.direction.value if hasattr(entry.direction, "value") else str(entry.direction),
                meta_json=entry.meta_json,
                created_at=entry.created_at,
            )
            for entry in entries
        ]
    )


@router.get("/ledger/{entry_id}/explain", response_model=LedgerExplainOut)
def explain_partner_ledger_entry(
    entry_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:finance:view")),
    db: Session = Depends(get_db),
) -> LedgerExplainOut:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    entry = db.query(PartnerLedgerEntry).filter(PartnerLedgerEntry.id == entry_id).one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="ledger_entry_not_found")
    if str(entry.partner_org_id) != str(partner_org_id):
        _audit_forbidden_access(
            principal=principal, request=request, db=db, entity_type="partner_ledger_entry", entity_id=str(entry.id)
        )
        raise HTTPException(status_code=403, detail="forbidden")
    meta = entry.meta_json or {}
    source_type = meta.get("source_type")
    source_id = meta.get("source_id")
    source_label = None
    formula = None
    if source_type in {"marketplace_order", "partner_order", "order"}:
        order_id = entry.order_id or source_id
        if order_id:
            order = db.query(MarketplaceOrder).filter(MarketplaceOrder.id == order_id).one_or_none()
            breakdown = order.settlement_breakdown_json if order else None
            if breakdown:
                gross = breakdown.get("gross_amount")
                fee = breakdown.get("platform_fee_amount")
                penalties = breakdown.get("penalties_amount")
                if gross is not None and fee is not None and penalties is not None:
                    formula = f"{gross} - {fee} - {penalties}"
            source_label = f"Order {order_id}"
    if source_type == "payout_request" and source_id:
        source_label = f"Payout request {source_id}"
    return LedgerExplainOut(
        entry_id=str(entry.id),
        operation=entry.entry_type.value if hasattr(entry.entry_type, "value") else str(entry.entry_type),
        amount=Decimal(entry.amount),
        currency=entry.currency,
        direction=entry.direction.value if hasattr(entry.direction, "value") else str(entry.direction),
        source_type=str(source_type) if source_type else None,
        source_id=str(source_id) if source_id else None,
        source_label=source_label,
        formula=formula,
    )


@router.post("/payouts/request", response_model=PartnerPayoutRequestOut, status_code=status.HTTP_201_CREATED)
def request_partner_payout(
    payload: PartnerPayoutRequestIn,
    principal: Principal = Depends(require_permission("partner:payouts:request")),
    db: Session = Depends(get_db),
) -> PartnerPayoutRequestOut:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_PAYOUT_REQUEST")
    service = PartnerFinanceService(db, request_ctx=request_context_from_request(None, token=principal.raw_claims))
    try:
        payout = service.request_payout(
            partner_org_id=partner_org_id,
            amount=payload.amount,
            currency=payload.currency,
            requested_by=str(principal.user_id) if principal.user_id else None,
        )
        db.commit()
        db.refresh(payout)
    except PartnerPayoutBlockedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "PAYOUT_BLOCKED", "reasons": exc.reasons},
        ) from exc
    except PartnerLegalError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail={"error": "LEGAL_NOT_VERIFIED", "reason": exc.code}) from exc
    except PartnerPayoutPolicyError as exc:
        db.rollback()
        reason = exc.reasons[0] if exc.reasons else "PAYOUT_BLOCKED"
        raise HTTPException(
            status_code=403,
            detail={"error": "PAYOUT_BLOCKED", "reason": reason, "reasons": exc.reasons},
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PartnerPayoutRequestOut(
        id=str(payout.id),
        partner_org_id=str(payout.partner_org_id),
        amount=Decimal(payout.amount),
        currency=payout.currency,
        status=payout.status.value if hasattr(payout.status, "value") else str(payout.status),
        requested_by=str(payout.requested_by) if payout.requested_by else None,
        approved_by=str(payout.approved_by) if payout.approved_by else None,
        created_at=payout.created_at,
        processed_at=payout.processed_at,
    )


@router.get("/payouts", response_model=PartnerPayoutListResponse)
def list_partner_payouts(
    principal: Principal = Depends(require_permission("partner:payouts:list")),
    db: Session = Depends(get_db),
) -> PartnerPayoutListResponse:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    items = (
        db.query(PartnerPayoutRequest)
        .filter(PartnerPayoutRequest.partner_org_id == partner_org_id)
        .order_by(PartnerPayoutRequest.created_at.desc())
        .all()
    )
    return PartnerPayoutListResponse(
        items=[
            PartnerPayoutRequestOut(
                id=str(item.id),
                partner_org_id=str(item.partner_org_id),
                amount=Decimal(item.amount),
                currency=item.currency,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                requested_by=str(item.requested_by) if item.requested_by else None,
                approved_by=str(item.approved_by) if item.approved_by else None,
                created_at=item.created_at,
                processed_at=item.processed_at,
            )
            for item in items
        ]
    )


@router.get("/payouts/{payout_id}/trace", response_model=PayoutTraceOut)
def trace_partner_payout(
    payout_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:payouts:list")),
    db: Session = Depends(get_db),
) -> PayoutTraceOut:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    batch = db.query(PayoutBatch).filter(PayoutBatch.id == payout_id).one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="payout_not_found")
    if str(batch.partner_id) != str(partner_org_id):
        _audit_forbidden_access(
            principal=principal, request=request, db=db, entity_type="payout_batch", entity_id=str(batch.id)
        )
        raise HTTPException(status_code=403, detail="forbidden")
    snapshot_ids: list[str] = []
    for item in batch.items or []:
        meta = item.meta or {}
        ids = meta.get("settlement_snapshot_ids") if isinstance(meta, dict) else None
        if ids:
            snapshot_ids.extend([str(value) for value in ids])
    snapshots = (
        db.query(MarketplaceSettlementSnapshot)
        .filter(MarketplaceSettlementSnapshot.id.in_(snapshot_ids))
        .all()
        if snapshot_ids
        else []
    )
    orders_by_snapshot = {str(snapshot.id): snapshot for snapshot in snapshots}
    order_rows: list[PayoutTraceOrderOut] = []
    gross_total = Decimal("0")
    fee_total = Decimal("0")
    penalties_total = Decimal("0")
    net_total = Decimal("0")
    for snapshot_id in snapshot_ids:
        snapshot = orders_by_snapshot.get(str(snapshot_id))
        if snapshot is None:
            continue
        gross = Decimal(snapshot.gross_amount or 0)
        fee = Decimal(snapshot.platform_fee or 0)
        penalties = Decimal(snapshot.penalties or 0)
        net = Decimal(snapshot.partner_net or 0)
        gross_total += gross
        fee_total += fee
        penalties_total += penalties
        net_total += net
        order_rows.append(
            PayoutTraceOrderOut(
                order_id=str(snapshot.order_id),
                gross_amount=gross,
                platform_fee=fee,
                penalties=penalties,
                partner_net=net,
                currency=snapshot.currency,
                settlement_snapshot_id=str(snapshot.id),
                finalized_at=snapshot.finalized_at,
                hash=snapshot.hash,
            )
        )
    state_value = batch.state.value if hasattr(batch.state, "value") else str(batch.state)
    return PayoutTraceOut(
        payout_id=str(batch.id),
        payout_state=state_value,
        date_from=batch.date_from,
        date_to=batch.date_to,
        created_at=batch.created_at,
        total_amount=Decimal(batch.total_amount or 0),
        summary=PayoutTraceSummaryOut(
            gross_total=gross_total,
            fee_total=fee_total,
            penalties_total=penalties_total,
            net_total=net_total,
        ),
        orders=order_rows,
    )


def _current_month_period() -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    start = date(today.year, today.month, 1)
    end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    return start, end


@router.get("/invoices", response_model=PartnerDocumentListResponse)
def list_partner_invoices(
    principal: Principal = Depends(require_permission("partner:documents:list")),
    db: Session = Depends(get_db),
) -> PartnerDocumentListResponse:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    period_from, period_to = _current_month_period()
    service = PartnerFinanceService(db)
    service.ensure_monthly_documents(
        partner_org_id=partner_org_id,
        period_from=period_from,
        period_to=period_to,
        currency="RUB",
    )
    db.commit()
    invoices = (
        db.query(PartnerInvoice)
        .filter(PartnerInvoice.partner_org_id == partner_org_id)
        .order_by(PartnerInvoice.period_from.desc())
        .all()
    )
    return PartnerDocumentListResponse(
        items=[
            PartnerDocumentOut(
                id=str(item.id),
                partner_org_id=str(item.partner_org_id),
                period_from=item.period_from,
                period_to=item.period_to,
                total_amount=Decimal(item.total_amount),
                currency=item.currency,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                tax_context=item.tax_context,
                pdf_object_key=item.pdf_object_key,
                created_at=item.created_at,
            )
            for item in invoices
        ]
    )


@router.get("/acts", response_model=PartnerDocumentListResponse)
def list_partner_acts(
    principal: Principal = Depends(require_permission("partner:documents:list")),
    db: Session = Depends(get_db),
) -> PartnerDocumentListResponse:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    period_from, period_to = _current_month_period()
    service = PartnerFinanceService(db)
    service.ensure_monthly_documents(
        partner_org_id=partner_org_id,
        period_from=period_from,
        period_to=period_to,
        currency="RUB",
    )
    db.commit()
    acts = (
        db.query(PartnerAct)
        .filter(PartnerAct.partner_org_id == partner_org_id)
        .order_by(PartnerAct.period_from.desc())
        .all()
    )
    return PartnerDocumentListResponse(
        items=[
            PartnerDocumentOut(
                id=str(item.id),
                partner_org_id=str(item.partner_org_id),
                period_from=item.period_from,
                period_to=item.period_to,
                total_amount=Decimal(item.total_amount),
                currency=item.currency,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                tax_context=item.tax_context,
                pdf_object_key=item.pdf_object_key,
                created_at=item.created_at,
            )
            for item in acts
        ]
    )


@router.get("/payouts/preview", response_model=PartnerPayoutPreviewOut)
def preview_partner_payout(
    principal: Principal = Depends(require_permission("partner:finance:view")),
    db: Session = Depends(get_db),
) -> PartnerPayoutPreviewOut:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    service = PartnerFinanceService(db)
    account = service.get_account(partner_org_id=partner_org_id, currency="RUB")
    policy = service.get_payout_policy(partner_org_id=partner_org_id, currency=account.currency)
    now = datetime.now(timezone.utc)
    payout_reasons = service.evaluate_payout_blockers(
        partner_org_id=partner_org_id,
        amount=Decimal(account.balance_available or 0),
        currency=account.currency,
        now=now,
    )
    legal_service = PartnerLegalService(db)
    profile = legal_service.get_profile(partner_id=partner_org_id)
    tax_context = legal_service.build_tax_context(profile=profile)
    warnings: list[str] = []
    legal_status = (
        profile.legal_status.value
        if profile and hasattr(profile.legal_status, "value")
        else (str(profile.legal_status) if profile else None)
    )
    if profile and profile.legal_status == PartnerLegalStatus.VERIFIED:
        details = legal_service.get_details(partner_id=partner_org_id)
        if details:
            warnings = legal_service.collect_warnings(profile=profile, details=details)
    return PartnerPayoutPreviewOut(
        partner_org_id=partner_org_id,
        currency=account.currency,
        available_amount=Decimal(account.balance_available or 0),
        min_payout_amount=Decimal(policy.min_payout_amount) if policy else None,
        payout_hold_days=int(policy.payout_hold_days) if policy else None,
        payout_schedule=policy.payout_schedule.value if policy else None,
        payout_block_reasons=payout_reasons,
        legal_status=legal_status,
        tax_context=tax_context.to_dict() if tax_context else None,
        warnings=warnings,
    )


@router.post("/exports/settlement-chain", response_model=PartnerExportJobCreateResponse, status_code=status.HTTP_201_CREATED)
def export_settlement_chain(
    payload: SettlementChainExportRequest,
    principal: Principal = Depends(require_permission("partner:finance:view")),
    db: Session = Depends(get_db),
) -> PartnerExportJobCreateResponse:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    user_id = _resolve_user_id(principal)
    if payload.format.value not in {"CSV", "ZIP"}:
        raise HTTPException(status_code=400, detail="format_not_supported")
    try:
        filters = normalize_filters(
            ExportJobReportType.SETTLEMENT_CHAIN,
            {"from": payload.from_.isoformat(), "to": payload.to.isoformat()},
        )
    except ExportRenderValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = ExportJob(
        org_id=str(partner_org_id),
        created_by_user_id=user_id,
        report_type=ExportJobReportType.SETTLEMENT_CHAIN,
        format=payload.format,
        filters_json=filters,
        status=ExportJobStatus.QUEUED,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(job)
    db.commit()
    export_metrics.mark_created(job.report_type.value, job.format.value)
    partner_trust_metrics.mark_export_generated()
    try:
        from app.celery_client import celery_client

        celery_client.send_task("exports.generate_export_job", args=[str(job.id)])
    except Exception as exc:  # noqa: BLE001
        job.status = ExportJobStatus.FAILED
        job.error_message = "celery_not_available"
        db.add(job)
        db.commit()
        export_metrics.mark_completed(job.report_type.value, job.format.value, job.status.value)
        export_metrics.mark_failure("celery")
        raise HTTPException(status_code=503, detail="celery_not_available") from exc
    return PartnerExportJobCreateResponse(id=str(job.id), status=job.status)


@router.get("/exports/jobs", response_model=PartnerExportJobListResponse)
def list_partner_export_jobs(
    principal: Principal = Depends(require_permission("partner:finance:view")),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
) -> PartnerExportJobListResponse:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    user_id = _resolve_user_id(principal)
    jobs = (
        db.query(ExportJob)
        .filter(ExportJob.org_id == str(partner_org_id))
        .filter(ExportJob.report_type == ExportJobReportType.SETTLEMENT_CHAIN)
        .filter(ExportJob.created_by_user_id == user_id)
        .order_by(ExportJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return PartnerExportJobListResponse(items=[_export_job_to_out(job) for job in jobs])


@router.get("/exports/jobs/{job_id}", response_model=PartnerExportJobOut)
def get_partner_export_job(
    job_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:finance:view")),
    db: Session = Depends(get_db),
) -> PartnerExportJobOut:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    user_id = _resolve_user_id(principal)
    job = db.query(ExportJob).filter(ExportJob.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="export_job_not_found")
    if str(job.org_id) != str(partner_org_id) or job.created_by_user_id != user_id:
        _audit_forbidden_access(
            principal=principal, request=request, db=db, entity_type="export_job", entity_id=str(job.id)
        )
        raise HTTPException(status_code=403, detail="forbidden")
    return _export_job_to_out(job)


@router.get("/exports/jobs/{job_id}/download")
def download_partner_export_job(
    job_id: str,
    request: Request,
    principal: Principal = Depends(require_permission("partner:finance:view")),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    partner_org_id = _ensure_capability(db, principal, "PARTNER_FINANCE_VIEW")
    user_id = _resolve_user_id(principal)
    job = db.query(ExportJob).filter(ExportJob.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="export_job_not_found")
    if str(job.org_id) != str(partner_org_id) or job.created_by_user_id != user_id:
        _audit_forbidden_access(
            principal=principal, request=request, db=db, entity_type="export_job", entity_id=str(job.id)
        )
        raise HTTPException(status_code=403, detail="forbidden")
    if job.expires_at and job.expires_at < datetime.now(timezone.utc):
        if job.status != ExportJobStatus.EXPIRED:
            job.status = ExportJobStatus.EXPIRED
            job.file_object_key = None
            job.content_type = None
            db.add(job)
            db.commit()
        raise HTTPException(status_code=410, detail="export_expired")
    if job.status == ExportJobStatus.EXPIRED:
        raise HTTPException(status_code=410, detail="export_expired")
    if job.status != ExportJobStatus.DONE or not job.file_object_key:
        raise HTTPException(status_code=400, detail="export_not_ready")
    storage = S3Storage(bucket=settings.NEFT_EXPORTS_BUCKET)
    signed_url = storage.presign(job.file_object_key, expires=settings.S3_SIGNED_URL_TTL_SECONDS)
    if not signed_url:
        raise HTTPException(status_code=503, detail="download_unavailable")
    return RedirectResponse(url=signed_url)
