from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.billing_flow import (
    BillingInvoice,
    BillingInvoiceStatus,
    BillingPayment,
    BillingPaymentStatus,
    BillingRefund,
    BillingRefundStatus,
)
from app.models.cases import CaseEventType, CaseKind, CasePriority
from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.models.reconciliation import (
    ReconciliationLink,
    ReconciliationLinkDirection,
    ReconciliationLinkStatus,
)
from app.services.billing_metrics import metrics as billing_metrics
from app.services.case_events_service import CaseEventActor, emit_case_event
from app.services.cases_service import create_case
from app.services.decision_memory.records import record_decision_memory
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService


LEDGER_REF_INVOICE = "BILLING_INVOICE"
LEDGER_REF_PAYMENT = "BILLING_PAYMENT"
LEDGER_REF_REFUND = "BILLING_REFUND"


@dataclass(frozen=True)
class BillingInvoiceResult:
    invoice: BillingInvoice
    is_replay: bool


@dataclass(frozen=True)
class BillingPaymentResult:
    payment: BillingPayment
    invoice: BillingInvoice
    is_replay: bool


@dataclass(frozen=True)
class BillingRefundResult:
    refund: BillingRefund
    payment: BillingPayment
    invoice: BillingInvoice
    is_replay: bool


def _normalize_currency(value: str) -> str:
    if not value:
        raise ValueError("currency_required")
    return value.upper()


def _require_positive_amount(amount: Decimal) -> None:
    if amount <= 0:
        raise ValueError("amount_must_be_positive")
    if amount != amount.to_integral_value():
        raise ValueError("amount_must_be_integer")


def _amount_to_int(amount: Decimal) -> int:
    _require_positive_amount(amount)
    return int(amount)


def _invoice_number() -> str:
    return f"INV-{uuid4().hex[:12].upper()}"


def _update_invoice_status(
    db: Session,
    *,
    invoice: BillingInvoice,
    actor: CaseEventActor | None,
    request_id: str | None,
    trace_id: str | None,
) -> None:
    paid_total = (
        db.query(func.coalesce(func.sum(BillingPayment.amount), 0))
        .filter(BillingPayment.invoice_id == invoice.id)
        .filter(BillingPayment.status != BillingPaymentStatus.FAILED)
        .scalar()
    )
    refunded_total = (
        db.query(func.coalesce(func.sum(BillingRefund.amount), 0))
        .join(BillingPayment, BillingRefund.payment_id == BillingPayment.id)
        .filter(BillingPayment.invoice_id == invoice.id)
        .filter(BillingRefund.status != BillingRefundStatus.FAILED)
        .scalar()
    )
    paid = Decimal(paid_total or 0) - Decimal(refunded_total or 0)
    new_status = BillingInvoiceStatus.ISSUED
    if paid <= 0:
        new_status = BillingInvoiceStatus.ISSUED
    elif paid < Decimal(invoice.amount_total):
        new_status = BillingInvoiceStatus.PARTIALLY_PAID
    else:
        new_status = BillingInvoiceStatus.PAID

    status_changed = invoice.status != new_status or Decimal(invoice.amount_paid or 0) != paid
    if not status_changed:
        return

    previous_status = invoice.status
    previous_paid = invoice.amount_paid
    invoice.status = new_status
    invoice.amount_paid = paid

    if invoice.case_id:
        emit_case_event(
            db,
            case_id=str(invoice.case_id),
            event_type=CaseEventType.INVOICE_STATUS_CHANGED,
            actor=actor,
            request_id=request_id,
            trace_id=trace_id,
            changes=None,
            extra_payload={
                "invoice_id": str(invoice.id),
                "previous_status": previous_status.value if previous_status else None,
                "new_status": new_status.value,
                "previous_amount_paid": str(previous_paid) if previous_paid is not None else None,
                "amount_paid": str(paid),
            },
        )


def _resolve_case_id(
    db: Session,
    *,
    tenant_id: int,
    case_id: str | None,
    invoice_number: str,
    actor: CaseEventActor | None,
    request_id: str | None,
    trace_id: str | None,
) -> str:
    if case_id:
        return case_id
    case = create_case(
        db,
        tenant_id=tenant_id,
        kind=CaseKind.INVOICE,
        entity_id=invoice_number,
        kpi_key=None,
        window_days=None,
        title=f"Billing invoice {invoice_number}",
        priority=CasePriority.MEDIUM,
        note=None,
        explain=None,
        diff=None,
        selected_actions=None,
        mastery_snapshot=None,
        created_by=actor.id if actor else None,
        request_id=request_id,
        trace_id=trace_id,
    )
    return str(case.id)


def issue_invoice(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    case_id: str | None,
    currency: str,
    amount_total: Decimal,
    due_at: datetime | None,
    idempotency_key: str,
    actor: CaseEventActor | None,
    request_id: str | None,
    trace_id: str | None,
) -> BillingInvoiceResult:
    currency_code = _normalize_currency(currency)
    _require_positive_amount(amount_total)

    existing = (
        db.query(BillingInvoice).filter(BillingInvoice.idempotency_key == idempotency_key).one_or_none()
    )
    if existing:
        if existing.currency != currency_code or Decimal(existing.amount_total) != amount_total:
            raise ValueError("idempotency_conflict")
        return BillingInvoiceResult(invoice=existing, is_replay=True)

    invoice_id = new_uuid_str()
    number = _invoice_number()
    resolved_case_id = _resolve_case_id(
        db,
        tenant_id=tenant_id,
        case_id=case_id,
        invoice_number=number,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
    )
    issued_at = datetime.now(timezone.utc)

    ledger_service = InternalLedgerService(db)
    amount_int = _amount_to_int(amount_total)
    ledger_result = ledger_service.post_transaction(
        tenant_id=tenant_id,
        transaction_type=InternalLedgerTransactionType.INVOICE_ISSUED,
        external_ref_type=LEDGER_REF_INVOICE,
        external_ref_id=invoice_id,
        idempotency_key=f"billing:invoice:{idempotency_key}",
        posted_at=issued_at,
        meta={"billing_invoice_id": invoice_id},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.CLIENT_AR,
                client_id=client_id,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount_int,
                currency=currency_code,
                meta={"billing_invoice_id": invoice_id},
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PLATFORM_REVENUE,
                client_id=None,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount_int,
                currency=currency_code,
                meta={"billing_invoice_id": invoice_id},
            ),
        ],
    )

    link = ReconciliationLink(
        entity_type="invoice",
        entity_id=invoice_id,
        provider="internal",
        currency=currency_code,
        expected_amount=amount_total,
        direction=ReconciliationLinkDirection.IN,
        expected_at=due_at or issued_at,
        match_key=number,
        status=ReconciliationLinkStatus.PENDING,
    )
    db.add(link)
    db.flush()

    event = emit_case_event(
        db,
        case_id=resolved_case_id,
        event_type=CaseEventType.INVOICE_ISSUED,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
        extra_payload={
            "invoice_id": invoice_id,
            "invoice_number": number,
            "client_id": client_id,
            "amount_total": str(amount_total),
            "currency": currency_code,
            "ledger_tx_id": str(ledger_result.transaction.id),
            "reconciliation_link_id": str(link.id),
        },
    )

    invoice = BillingInvoice(
        id=invoice_id,
        invoice_number=number,
        client_id=client_id,
        case_id=resolved_case_id,
        currency=currency_code,
        amount_total=amount_total,
        amount_paid=Decimal("0"),
        status=BillingInvoiceStatus.ISSUED,
        issued_at=issued_at,
        due_at=due_at,
        idempotency_key=idempotency_key,
        ledger_tx_id=ledger_result.transaction.id,
        audit_event_id=event.id,
    )
    db.add(invoice)

    record_decision_memory(
        db,
        case_id=resolved_case_id,
        decision_type="billing_invoice",
        decision_ref_id=invoice_id,
        decision_at=issued_at,
        decided_by_user_id=actor.id if actor else None,
        context_snapshot={"amount_total": str(amount_total), "currency": currency_code},
        rationale=None,
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=str(event.id),
    )

    billing_metrics.mark_invoice_issued()
    return BillingInvoiceResult(invoice=invoice, is_replay=False)


def capture_payment(
    db: Session,
    *,
    tenant_id: int,
    invoice_id: str,
    provider: str,
    provider_payment_id: str | None,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    actor: CaseEventActor | None,
    request_id: str | None,
    trace_id: str | None,
) -> BillingPaymentResult:
    currency_code = _normalize_currency(currency)
    _require_positive_amount(amount)

    existing = (
        db.query(BillingPayment).filter(BillingPayment.idempotency_key == idempotency_key).one_or_none()
    )
    if existing:
        if existing.currency != currency_code or Decimal(existing.amount) != amount:
            raise ValueError("idempotency_conflict")
        invoice = db.query(BillingInvoice).filter(BillingInvoice.id == existing.invoice_id).one()
        return BillingPaymentResult(payment=existing, invoice=invoice, is_replay=True)

    invoice = db.query(BillingInvoice).filter(BillingInvoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise ValueError("invoice_not_found")
    if invoice.currency != currency_code:
        raise ValueError("currency_mismatch")

    payment_id = new_uuid_str()
    captured_at = datetime.now(timezone.utc)

    ledger_service = InternalLedgerService(db)
    amount_int = _amount_to_int(amount)
    ledger_result = ledger_service.post_transaction(
        tenant_id=tenant_id,
        transaction_type=InternalLedgerTransactionType.PAYMENT_APPLIED,
        external_ref_type=LEDGER_REF_PAYMENT,
        external_ref_id=payment_id,
        idempotency_key=f"billing:payment:{idempotency_key}",
        posted_at=captured_at,
        meta={"billing_payment_id": payment_id, "invoice_id": invoice_id, "provider": provider},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PROVIDER_PAYABLE,
                client_id=provider,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount_int,
                currency=currency_code,
                meta={"billing_payment_id": payment_id, "invoice_id": invoice_id},
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.CLIENT_AR,
                client_id=str(invoice.client_id),
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount_int,
                currency=currency_code,
                meta={"billing_payment_id": payment_id, "invoice_id": invoice_id},
            ),
        ],
    )

    link = ReconciliationLink(
        entity_type="payment",
        entity_id=payment_id,
        provider=provider,
        currency=currency_code,
        expected_amount=amount,
        direction=ReconciliationLinkDirection.IN,
        expected_at=captured_at,
        match_key=provider_payment_id,
        status=ReconciliationLinkStatus.PENDING,
    )
    db.add(link)
    db.flush()

    event = emit_case_event(
        db,
        case_id=str(invoice.case_id),
        event_type=CaseEventType.PAYMENT_CAPTURED,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
        extra_payload={
            "invoice_id": invoice_id,
            "payment_id": payment_id,
            "amount": str(amount),
            "currency": currency_code,
            "provider": provider,
            "provider_payment_id": provider_payment_id,
            "ledger_tx_id": str(ledger_result.transaction.id),
            "reconciliation_link_id": str(link.id),
        },
    )

    payment = BillingPayment(
        id=payment_id,
        invoice_id=invoice_id,
        provider=provider,
        provider_payment_id=provider_payment_id,
        currency=currency_code,
        amount=amount,
        captured_at=captured_at,
        status=BillingPaymentStatus.CAPTURED,
        idempotency_key=idempotency_key,
        ledger_tx_id=ledger_result.transaction.id,
        external_statement_line_id=None,
        audit_event_id=event.id,
    )
    db.add(payment)

    record_decision_memory(
        db,
        case_id=str(invoice.case_id),
        decision_type="billing_payment",
        decision_ref_id=payment_id,
        decision_at=captured_at,
        decided_by_user_id=actor.id if actor else None,
        context_snapshot={"amount": str(amount), "currency": currency_code, "provider": provider},
        rationale=None,
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=str(event.id),
    )

    _update_invoice_status(
        db,
        invoice=invoice,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
    )

    billing_metrics.mark_payment_captured()
    return BillingPaymentResult(payment=payment, invoice=invoice, is_replay=False)


def refund_payment(
    db: Session,
    *,
    tenant_id: int,
    payment_id: str,
    provider_refund_id: str | None,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    actor: CaseEventActor | None,
    request_id: str | None,
    trace_id: str | None,
) -> BillingRefundResult:
    currency_code = _normalize_currency(currency)
    _require_positive_amount(amount)

    existing = (
        db.query(BillingRefund).filter(BillingRefund.idempotency_key == idempotency_key).one_or_none()
    )
    if existing:
        if existing.currency != currency_code or Decimal(existing.amount) != amount:
            raise ValueError("idempotency_conflict")
        payment = db.query(BillingPayment).filter(BillingPayment.id == existing.payment_id).one()
        invoice = db.query(BillingInvoice).filter(BillingInvoice.id == payment.invoice_id).one()
        return BillingRefundResult(refund=existing, payment=payment, invoice=invoice, is_replay=True)

    payment = db.query(BillingPayment).filter(BillingPayment.id == payment_id).one_or_none()
    if payment is None:
        raise ValueError("payment_not_found")
    if payment.currency != currency_code:
        raise ValueError("currency_mismatch")

    invoice = db.query(BillingInvoice).filter(BillingInvoice.id == payment.invoice_id).one()

    refund_id = new_uuid_str()
    refunded_at = datetime.now(timezone.utc)

    ledger_service = InternalLedgerService(db)
    amount_int = _amount_to_int(amount)
    ledger_result = ledger_service.post_transaction(
        tenant_id=tenant_id,
        transaction_type=InternalLedgerTransactionType.REFUND_APPLIED,
        external_ref_type=LEDGER_REF_REFUND,
        external_ref_id=refund_id,
        idempotency_key=f"billing:refund:{idempotency_key}",
        posted_at=refunded_at,
        meta={"billing_refund_id": refund_id, "payment_id": payment_id, "provider": payment.provider},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.CLIENT_AR,
                client_id=str(invoice.client_id),
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount_int,
                currency=currency_code,
                meta={"billing_refund_id": refund_id, "payment_id": payment_id},
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PROVIDER_PAYABLE,
                client_id=payment.provider,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount_int,
                currency=currency_code,
                meta={"billing_refund_id": refund_id, "payment_id": payment_id},
            ),
        ],
    )

    link = ReconciliationLink(
        entity_type="refund",
        entity_id=refund_id,
        provider=payment.provider,
        currency=currency_code,
        expected_amount=amount,
        direction=ReconciliationLinkDirection.OUT,
        expected_at=refunded_at,
        match_key=provider_refund_id,
        status=ReconciliationLinkStatus.PENDING,
    )
    db.add(link)
    db.flush()

    event = emit_case_event(
        db,
        case_id=str(invoice.case_id),
        event_type=CaseEventType.PAYMENT_REFUNDED,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
        extra_payload={
            "invoice_id": str(invoice.id),
            "payment_id": payment_id,
            "refund_id": refund_id,
            "amount": str(amount),
            "currency": currency_code,
            "provider": payment.provider,
            "provider_refund_id": provider_refund_id,
            "ledger_tx_id": str(ledger_result.transaction.id),
            "reconciliation_link_id": str(link.id),
        },
    )

    refund = BillingRefund(
        id=refund_id,
        payment_id=payment_id,
        provider_refund_id=provider_refund_id,
        currency=currency_code,
        amount=amount,
        refunded_at=refunded_at,
        status=BillingRefundStatus.REFUNDED,
        idempotency_key=idempotency_key,
        ledger_tx_id=ledger_result.transaction.id,
        external_statement_line_id=None,
        audit_event_id=event.id,
    )
    db.add(refund)

    record_decision_memory(
        db,
        case_id=str(invoice.case_id),
        decision_type="billing_refund",
        decision_ref_id=refund_id,
        decision_at=refunded_at,
        decided_by_user_id=actor.id if actor else None,
        context_snapshot={"amount": str(amount), "currency": currency_code, "provider": payment.provider},
        rationale=None,
        score_snapshot=None,
        mastery_snapshot=None,
        audit_event_id=str(event.id),
    )

    payment_refunded = (
        db.query(func.coalesce(func.sum(BillingRefund.amount), 0))
        .filter(BillingRefund.payment_id == payment_id)
        .filter(BillingRefund.status != BillingRefundStatus.FAILED)
        .scalar()
    )
    if Decimal(payment_refunded or 0) >= Decimal(payment.amount):
        payment.status = BillingPaymentStatus.REFUNDED_FULL
    else:
        payment.status = BillingPaymentStatus.REFUNDED_PARTIAL

    _update_invoice_status(
        db,
        invoice=invoice,
        actor=actor,
        request_id=request_id,
        trace_id=trace_id,
    )

    billing_metrics.mark_refund()
    return BillingRefundResult(refund=refund, payment=payment, invoice=invoice, is_replay=False)


__all__ = [
    "BillingInvoiceResult",
    "BillingPaymentResult",
    "BillingRefundResult",
    "capture_payment",
    "issue_invoice",
    "refund_payment",
]
