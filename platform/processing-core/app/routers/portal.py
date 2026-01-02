from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.models.audit_log import AuditVisibility
from app.models.finance import CreditNote, InvoicePayment
from app.models.invoice import Invoice, InvoiceStatus
from app.models.marketplace_contracts import Contract, ContractObligation, ContractStatus, SLAResult
from app.models.settlement_v1 import SettlementItem, SettlementPeriod, SettlementPayout
from app.schemas.portal import (
    ClientContractDetails,
    ClientContractsResponse,
    ClientContractSummary,
    ClientDashboardResponse,
    ClientInvoiceDetails,
    ClientInvoiceListResponse,
    ClientInvoicePaymentSummary,
    ClientInvoiceRefundSummary,
    ClientInvoiceSummary,
    ContractObligationSummary,
    PartnerContractSummary,
    PartnerContractsResponse,
    PartnerDashboardResponse,
    PartnerSettlementDetails,
    PartnerSettlementItemSummary,
    PartnerSettlementListResponse,
    PartnerSettlementSummary,
    PortalSlaSummary,
    SlaResultSummary,
)
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.s3_storage import S3Storage

client_router = APIRouter(prefix="/client", tags=["client-portal-v1"])
partner_router = APIRouter(prefix="/partner", tags=["partner-portal-v1"])


def _ensure_client_context(token: dict) -> str:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Missing client context")
    return str(client_id)


def _ensure_partner_context(token: dict) -> str:
    partner_id = token.get("partner_id")
    if not partner_id:
        raise HTTPException(status_code=403, detail="Missing partner context")
    return str(partner_id)


def _public_invoice_number(invoice: Invoice) -> str:
    if invoice.number:
        return invoice.number
    if invoice.external_number:
        return invoice.external_number
    return "UNASSIGNED"


def _resolve_invoice(db: Session, *, invoice_ref: str, client_id: str) -> Invoice | None:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_ref).one_or_none()
    if invoice and invoice.client_id == client_id:
        return invoice
    return (
        db.query(Invoice)
        .filter(
            Invoice.client_id == client_id,
            (Invoice.number == invoice_ref) | (Invoice.external_number == invoice_ref),
        )
        .one_or_none()
    )


def _contract_query(db: Session, *, party_id: str) -> list[Contract]:
    return (
        db.query(Contract)
        .filter((Contract.party_a_id == UUID(party_id)) | (Contract.party_b_id == UUID(party_id)))
        .order_by(Contract.effective_from.desc(), Contract.created_at.desc())
        .all()
    )


def _resolve_contract(db: Session, *, contract_ref: str, party_id: str) -> Contract | None:
    contract = db.query(Contract).filter(Contract.id == contract_ref).one_or_none()
    if contract and (str(contract.party_a_id) == party_id or str(contract.party_b_id) == party_id):
        return contract
    return (
        db.query(Contract)
        .filter(
            Contract.contract_number == contract_ref,
            (Contract.party_a_id == UUID(party_id)) | (Contract.party_b_id == UUID(party_id)),
        )
        .one_or_none()
    )


def _sla_summary(db: Session, *, contract_ids: list[str]) -> PortalSlaSummary:
    if not contract_ids:
        return PortalSlaSummary(status="OK", violations=0)
    results = db.query(SLAResult.status).filter(SLAResult.contract_id.in_(contract_ids)).all()
    violations = sum(1 for (status,) in results if str(status).upper() != "OK")
    return PortalSlaSummary(status="VIOLATIONS" if violations else "OK", violations=violations)


def _contract_sla_stats(db: Session, *, contract_id: str) -> tuple[int, str]:
    statuses = db.query(SLAResult.status).filter(SLAResult.contract_id == contract_id).all()
    violations = sum(1 for (status,) in statuses if str(status).upper() != "OK")
    return violations, "VIOLATIONS" if violations else "OK"


@client_router.get("/dashboard", response_model=ClientDashboardResponse)
def client_dashboard(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientDashboardResponse:
    client_id = _ensure_client_context(token)
    active_contracts = db.query(Contract).filter(
        (Contract.party_a_id == UUID(client_id)) | (Contract.party_b_id == UUID(client_id)),
        Contract.status == ContractStatus.ACTIVE.value,
    )
    active_contracts_count = active_contracts.count()

    due_statuses = {InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE}
    due_query = db.query(Invoice).filter(Invoice.client_id == client_id, Invoice.status.in_(due_statuses))
    invoices_due = due_query.count()
    invoices_due_amount = due_query.with_entities(func.coalesce(func.sum(Invoice.amount_due), 0)).scalar() or 0

    since = datetime.now(timezone.utc) - timedelta(days=30)
    payments_query = (
        db.query(InvoicePayment)
        .join(Invoice, Invoice.id == InvoicePayment.invoice_id)
        .filter(Invoice.client_id == client_id, InvoicePayment.created_at >= since)
    )
    payments_sum = payments_query.with_entities(func.coalesce(func.sum(InvoicePayment.amount), 0)).scalar() or 0
    payments_count = payments_query.count()

    contract_ids = [str(row.id) for row in active_contracts.with_entities(Contract.id).all()]
    sla_summary = _sla_summary(db, contract_ids=contract_ids)

    return ClientDashboardResponse(
        active_contracts=active_contracts_count,
        invoices_due=invoices_due,
        invoices_due_amount=Decimal(invoices_due_amount),
        payments_last_30d=Decimal(payments_sum),
        payments_last_30d_count=payments_count,
        sla=sla_summary,
    )


@client_router.get("/invoices", response_model=ClientInvoiceListResponse)
def list_client_invoices(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    status: list[InvoiceStatus] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientInvoiceListResponse:
    client_id = _ensure_client_context(token)
    query = db.query(Invoice).filter(Invoice.client_id == client_id)
    if date_from:
        query = query.filter(Invoice.period_from >= date_from)
    if date_to:
        query = query.filter(Invoice.period_to <= date_to)
    if status:
        query = query.filter(Invoice.status.in_(status))

    total = query.count()
    invoices = (
        query.order_by(Invoice.issued_at.desc().nullslast(), Invoice.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        ClientInvoiceSummary(
            invoice_number=_public_invoice_number(invoice),
            period_start=invoice.period_from,
            period_end=invoice.period_to,
            amount_total=Decimal(invoice.total_with_tax or invoice.total_amount or 0),
            status=invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
            due_date=invoice.due_date,
            currency=invoice.currency,
        )
        for invoice in invoices
    ]
    return ClientInvoiceListResponse(items=items, total=total, limit=limit, offset=offset)


@client_router.get("/invoices/{invoice_ref}", response_model=ClientInvoiceDetails)
def get_client_invoice_details(
    invoice_ref: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientInvoiceDetails:
    client_id = _ensure_client_context(token)
    invoice = _resolve_invoice(db, invoice_ref=invoice_ref, client_id=client_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")

    payments = (
        db.query(InvoicePayment)
        .filter(InvoicePayment.invoice_id == invoice.id)
        .order_by(InvoicePayment.created_at.desc())
        .all()
    )
    refunds = (
        db.query(CreditNote)
        .filter(CreditNote.invoice_id == invoice.id)
        .order_by(CreditNote.created_at.desc())
        .all()
    )

    AuditService(db).audit(
        event_type="CLIENT_VIEWED_INVOICE",
        entity_type="invoice",
        entity_id=str(invoice.id),
        action="VIEW",
        visibility=AuditVisibility.INTERNAL,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    return ClientInvoiceDetails(
        invoice_number=_public_invoice_number(invoice),
        period_start=invoice.period_from,
        period_end=invoice.period_to,
        amount_total=Decimal(invoice.total_with_tax or invoice.total_amount or 0),
        amount_paid=Decimal(invoice.amount_paid or 0),
        amount_refunded=Decimal(invoice.amount_refunded or 0),
        amount_due=Decimal(invoice.amount_due or 0),
        status=invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
        due_date=invoice.due_date,
        currency=invoice.currency,
        download_url=(
            f"/api/client/invoices/{_public_invoice_number(invoice)}/download"
            if invoice.pdf_object_key and _public_invoice_number(invoice) != "UNASSIGNED"
            else None
        ),
        payments=[
            ClientInvoicePaymentSummary(
                amount=Decimal(payment.amount or 0),
                status=payment.status.value if hasattr(payment.status, "value") else str(payment.status),
                provider=payment.provider,
                external_ref=payment.external_ref,
                created_at=payment.created_at,
            )
            for payment in payments
        ],
        refunds=[
            ClientInvoiceRefundSummary(
                amount=Decimal(refund.amount or 0),
                status=refund.status.value if hasattr(refund.status, "value") else str(refund.status),
                provider=refund.provider,
                external_ref=refund.external_ref,
                created_at=refund.created_at,
                reason=refund.reason,
            )
            for refund in refunds
        ],
    )


@client_router.get("/invoices/{invoice_ref}/download")
def download_client_invoice(
    invoice_ref: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> Response:
    client_id = _ensure_client_context(token)
    invoice = _resolve_invoice(db, invoice_ref=invoice_ref, client_id=client_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    if not invoice.pdf_object_key:
        raise HTTPException(status_code=404, detail="invoice_pdf_not_found")

    storage = S3Storage()
    pdf_bytes = storage.get_bytes(invoice.pdf_object_key)

    AuditService(db).audit(
        event_type="CLIENT_DOWNLOADED_INVOICE",
        entity_type="invoice",
        entity_id=str(invoice.id),
        action="DOWNLOAD",
        visibility=AuditVisibility.INTERNAL,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )

    filename = f"{_public_invoice_number(invoice)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@client_router.get("/contracts", response_model=ClientContractsResponse)
def list_client_contracts(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientContractsResponse:
    client_id = _ensure_client_context(token)
    contracts = _contract_query(db, party_id=client_id)
    items = []
    for contract in contracts:
        violations, status = _contract_sla_stats(db, contract_id=str(contract.id))
        items.append(
            ClientContractSummary(
                contract_number=contract.contract_number,
                contract_type=contract.contract_type,
                effective_from=contract.effective_from,
                effective_to=contract.effective_to,
                status=contract.status,
                sla_status=status,
                sla_violations=violations,
            )
        )
    return ClientContractsResponse(items=items)


@client_router.get("/contracts/{contract_ref}", response_model=ClientContractDetails)
def get_client_contract_details(
    contract_ref: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientContractDetails:
    client_id = _ensure_client_context(token)
    contract = _resolve_contract(db, contract_ref=contract_ref, party_id=client_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="contract_not_found")
    contract_id = str(contract.id)

    obligations = (
        db.query(ContractObligation).filter(ContractObligation.contract_id == contract_id).order_by(ContractObligation.created_at.asc()).all()
    )
    sla_results = (
        db.query(SLAResult)
        .filter(SLAResult.contract_id == contract_id)
        .order_by(SLAResult.period_start.desc())
        .limit(50)
        .all()
    )
    violations, status = _contract_sla_stats(db, contract_id=contract_id)
    penalty_total = Decimal(0)
    obligation_map = {str(item.id): item for item in obligations}
    for result in sla_results:
        if str(result.status).upper() != "OK":
            obligation = obligation_map.get(str(result.obligation_id))
            if obligation:
                penalty_total += Decimal(obligation.penalty_value or 0)

    return ClientContractDetails(
        contract_number=contract.contract_number,
        contract_type=contract.contract_type,
        effective_from=contract.effective_from,
        effective_to=contract.effective_to,
        status=contract.status,
        sla_status=status,
        sla_violations=violations,
        penalties_total=penalty_total,
        obligations=[
            ContractObligationSummary(
                obligation_type=item.obligation_type,
                metric=item.metric,
                threshold=Decimal(item.threshold),
                comparison=item.comparison,
                window=item.window,
                penalty_type=item.penalty_type,
                penalty_value=Decimal(item.penalty_value),
            )
            for item in obligations
        ],
        sla_results=[
            SlaResultSummary(
                period_start=result.period_start,
                period_end=result.period_end,
                status=result.status,
                measured_value=Decimal(result.measured_value),
            )
            for result in sla_results
        ],
    )


@partner_router.get("/dashboard", response_model=PartnerDashboardResponse)
def partner_dashboard(
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> PartnerDashboardResponse:
    partner_id = _ensure_partner_context(token)
    contracts = _contract_query(db, party_id=partner_id)
    active_contracts = sum(1 for contract in contracts if contract.status == ContractStatus.ACTIVE.value)

    settlement = (
        db.query(SettlementPeriod)
        .filter(SettlementPeriod.partner_id == UUID(partner_id))
        .order_by(SettlementPeriod.period_end.desc())
        .first()
    )
    current_period = None
    upcoming_payout = None
    if settlement:
        current_period = f"{settlement.period_start.date().isoformat()} — {settlement.period_end.date().isoformat()}"
        payout = (
            db.query(SettlementPayout)
            .filter(SettlementPayout.settlement_period_id == settlement.id)
            .order_by(SettlementPayout.created_at.desc())
            .first()
        )
        if payout:
            upcoming_payout = Decimal(payout.amount)

    contract_ids = [str(contract.id) for contract in contracts]
    sla_summary = _sla_summary(db, contract_ids=contract_ids)

    return PartnerDashboardResponse(
        active_contracts=active_contracts,
        current_settlement_period=current_period,
        upcoming_payout=upcoming_payout,
        sla_score=None,
        sla=sla_summary,
    )


@partner_router.get("/contracts", response_model=PartnerContractsResponse)
def list_partner_contracts(
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> PartnerContractsResponse:
    partner_id = _ensure_partner_context(token)
    contracts = _contract_query(db, party_id=partner_id)
    items = []
    for contract in contracts:
        violations, status = _contract_sla_stats(db, contract_id=str(contract.id))
        items.append(
            PartnerContractSummary(
                contract_number=contract.contract_number,
                contract_type=contract.contract_type,
                effective_from=contract.effective_from,
                effective_to=contract.effective_to,
                status=contract.status,
                sla_status=status,
                sla_violations=violations,
            )
        )
    return PartnerContractsResponse(items=items)


@partner_router.get("/settlements", response_model=PartnerSettlementListResponse)
def list_partner_settlements(
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> PartnerSettlementListResponse:
    partner_id = _ensure_partner_context(token)
    settlements = (
        db.query(SettlementPeriod)
        .filter(SettlementPeriod.partner_id == UUID(partner_id))
        .order_by(SettlementPeriod.period_start.desc())
        .all()
    )
    items = [
        PartnerSettlementSummary(
            settlement_ref=str(settlement.id),
            period_start=settlement.period_start,
            period_end=settlement.period_end,
            gross=Decimal(settlement.total_gross or 0),
            fees=Decimal(settlement.total_fees or 0),
            refunds=Decimal(settlement.total_refunds or 0),
            net_amount=Decimal(settlement.net_amount or 0),
            status=settlement.status.value if hasattr(settlement.status, "value") else str(settlement.status),
            currency=settlement.currency,
        )
        for settlement in settlements
    ]
    return PartnerSettlementListResponse(items=items)


@partner_router.get("/settlements/{settlement_id}", response_model=PartnerSettlementDetails)
def get_partner_settlement_details(
    settlement_id: str,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> PartnerSettlementDetails:
    partner_id = _ensure_partner_context(token)
    settlement = db.query(SettlementPeriod).filter(SettlementPeriod.id == settlement_id).one_or_none()
    if settlement is None:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    if str(settlement.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")

    items = (
        db.query(
            SettlementItem.source_type,
            SettlementItem.direction,
            func.count(SettlementItem.id),
            func.coalesce(func.sum(SettlementItem.amount), 0),
        )
        .filter(SettlementItem.settlement_period_id == settlement_id)
        .group_by(SettlementItem.source_type, SettlementItem.direction)
        .all()
    )
    payout = (
        db.query(SettlementPayout)
        .filter(SettlementPayout.settlement_period_id == settlement_id)
        .order_by(SettlementPayout.created_at.desc())
        .first()
    )

    return PartnerSettlementDetails(
        settlement_ref=str(settlement.id),
        period_start=settlement.period_start,
        period_end=settlement.period_end,
        gross=Decimal(settlement.total_gross or 0),
        fees=Decimal(settlement.total_fees or 0),
        refunds=Decimal(settlement.total_refunds or 0),
        net_amount=Decimal(settlement.net_amount or 0),
        status=settlement.status.value if hasattr(settlement.status, "value") else str(settlement.status),
        currency=settlement.currency,
        items_summary=[
            PartnerSettlementItemSummary(
                source_type=str(source_type),
                direction=str(direction),
                count=int(count),
                amount=Decimal(amount),
            )
            for source_type, direction, count, amount in items
        ],
        payout_status=payout.status.value if payout and hasattr(payout.status, "value") else (str(payout.status) if payout else None),
    )


@partner_router.post("/settlements/{settlement_id}/confirm", status_code=status.HTTP_202_ACCEPTED)
def confirm_partner_settlement(
    settlement_id: str,
    request: Request,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> dict:
    partner_id = _ensure_partner_context(token)
    settlement = db.query(SettlementPeriod).filter(SettlementPeriod.id == settlement_id).one_or_none()
    if settlement is None:
        raise HTTPException(status_code=404, detail="settlement_not_found")
    if str(settlement.partner_id) != partner_id:
        raise HTTPException(status_code=403, detail="forbidden")

    AuditService(db).audit(
        event_type="PARTNER_CONFIRMED_PAYOUT",
        entity_type="settlement",
        entity_id=settlement_id,
        action="CONFIRM_PAYOUT",
        visibility=AuditVisibility.INTERNAL,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        reason="partner_portal_stub",
    )
    return {"status": "queued"}
