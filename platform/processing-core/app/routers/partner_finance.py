from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.partner_finance import PartnerAct, PartnerInvoice, PartnerLedgerEntry, PartnerPayoutRequest
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
from app.security.rbac.guard import require_permission
from app.security.rbac.principal import Principal
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.partner_finance_service import PartnerFinanceService
from app.services.audit_service import request_context_from_request
from app.models.partner_legal import PartnerLegalStatus
from app.services.partner_legal_service import PartnerLegalError, PartnerLegalService

router = APIRouter(prefix="/partner", tags=["partner-finance"])


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
    except PartnerLegalError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail={"error": "LEGAL_NOT_VERIFIED", "reason": exc.code}) from exc
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
    account = PartnerFinanceService(db).get_account(partner_org_id=partner_org_id, currency="RUB")
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
        legal_status=legal_status,
        tax_context=tax_context.to_dict() if tax_context else None,
        warnings=warnings,
    )
