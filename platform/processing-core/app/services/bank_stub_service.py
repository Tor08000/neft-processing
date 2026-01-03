from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_log import AuditVisibility
from app.models.bank_stub import (
    BankStubPayment,
    BankStubPaymentStatus,
    BankStubStatement,
    BankStubStatementLine,
)
from app.models.billing_flow import BillingInvoice
from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.billing_service import BillingPaymentResult, capture_payment
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService
from app.services.job_locks import advisory_lock, make_lock_token, make_stable_key


class BankStubServiceError(Exception):
    """Domain error for bank stub provider."""


def _canonical_json(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash_payload(data: object) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _require_enabled() -> None:
    if not settings.BANK_STUB_ENABLED:
        raise BankStubServiceError("bank_stub_disabled")


def _payment_ref(scope_key: str) -> str:
    return f"BSTUB-{scope_key[:12].upper()}"


def _statement_payload(
    *,
    period_from: datetime,
    period_to: datetime,
    currency: str | None,
    lines: list[dict[str, object]],
    total_in: Decimal,
) -> dict[str, object]:
    return {
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "currency": currency,
        "total_in": str(total_in),
        "lines": lines,
    }


def _extract_currency(payments: Iterable[BankStubPayment]) -> str | None:
    currencies = {payment.currency for payment in payments}
    if not currencies:
        return None
    if len(currencies) > 1:
        raise BankStubServiceError("bank_stub_multiple_currencies")
    return currencies.pop()


def create_stub_payment(
    db: Session,
    *,
    tenant_id: int,
    invoice_id: str,
    amount: Decimal | None,
    idempotency_key: str | None,
    actor: RequestContext | None,
) -> tuple[BankStubPayment, BillingPaymentResult]:
    _require_enabled()
    invoice = db.query(BillingInvoice).filter(BillingInvoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise BankStubServiceError("invoice_not_found")

    default_amount = Decimal(invoice.amount_total or 0) - Decimal(invoice.amount_paid or 0)
    if default_amount <= 0:
        default_amount = Decimal(invoice.amount_total or 0)
    payment_amount = amount if amount is not None else default_amount
    if payment_amount <= 0:
        raise BankStubServiceError("amount_invalid")

    scope_key = make_stable_key(
        "bank_stub_payment",
        {"invoice_id": invoice_id, "amount": str(payment_amount)},
        idempotency_key,
    )
    lock_token = make_lock_token("bank_stub_payment", scope_key)
    with advisory_lock(db, lock_token) as acquired:
        if not acquired:
            raise BankStubServiceError("bank_stub_payment_locked")

        existing = db.query(BankStubPayment).filter(BankStubPayment.idempotency_key == scope_key).one_or_none()
        if existing:
            billing_payment = capture_payment(
                db,
                tenant_id=tenant_id,
                invoice_id=invoice_id,
                provider="bank_stub",
                provider_payment_id=existing.payment_ref,
                amount=payment_amount,
                currency=invoice.currency,
                idempotency_key=scope_key,
                actor=None,
                request_id=None,
                trace_id=None,
            )
            return existing, billing_payment

        payment_ref = _payment_ref(scope_key)
        status = BankStubPaymentStatus.SETTLED if settings.BANK_STUB_IMMEDIATE_SETTLE else BankStubPaymentStatus.POSTED
        bank_payment = BankStubPayment(
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            payment_ref=payment_ref,
            amount=payment_amount,
            currency=invoice.currency,
            status=status,
            idempotency_key=scope_key,
        )
        db.add(bank_payment)
        db.flush()

        billing_payment = capture_payment(
            db,
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            provider="bank_stub",
            provider_payment_id=payment_ref,
            amount=payment_amount,
            currency=invoice.currency,
            idempotency_key=scope_key,
            actor=None,
            request_id=None,
            trace_id=None,
        )

        _post_settlement_allocation(
            db,
            tenant_id=tenant_id,
            partner_id=str(invoice.client_id),
            currency=invoice.currency,
            amount=payment_amount,
            payment_id=billing_payment.payment.id,
            posted_at=datetime.now(timezone.utc),
        )

        AuditService(db).audit(
            event_type="BANK_STUB_PAYMENT_CREATED",
            entity_type="bank_stub_payment",
            entity_id=str(bank_payment.id),
            action="created",
            visibility=AuditVisibility.INTERNAL,
            after={
                "invoice_id": invoice_id,
                "payment_ref": payment_ref,
                "amount": str(payment_amount),
                "currency": invoice.currency,
                "billing_payment_id": str(billing_payment.payment.id),
            },
            request_ctx=actor,
        )
        return bank_payment, billing_payment


def _post_settlement_allocation(
    db: Session,
    *,
    tenant_id: int,
    partner_id: str,
    currency: str,
    amount: Decimal,
    payment_id: str,
    posted_at: datetime,
) -> None:
    ledger_service = InternalLedgerService(db)
    amount_minor = int((amount * Decimal("100")).to_integral_value())
    ledger_service.post_transaction(
        tenant_id=tenant_id,
        transaction_type=InternalLedgerTransactionType.SETTLEMENT_ALLOCATION_CREATED,
        external_ref_type="BILLING_PAYMENT",
        external_ref_id=payment_id,
        idempotency_key=f"bank_stub:settlement:{payment_id}",
        posted_at=posted_at,
        meta={"source_type": "payment", "source_id": payment_id},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.PARTNER_SETTLEMENT,
                client_id=partner_id,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount_minor,
                currency=currency,
                meta={"source_type": "payment", "source_id": payment_id},
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.SETTLEMENT_CLEARING,
                client_id=None,
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount_minor,
                currency=currency,
                meta={"source_type": "payment", "source_id": payment_id},
            ),
        ],
    )


def get_stub_payment(db: Session, payment_id: str) -> BankStubPayment | None:
    _require_enabled()
    return db.query(BankStubPayment).filter(BankStubPayment.id == payment_id).one_or_none()


def generate_statement(
    db: Session,
    *,
    tenant_id: int,
    period_from: datetime,
    period_to: datetime,
    actor: RequestContext | None,
) -> BankStubStatement:
    _require_enabled()
    if period_from > period_to:
        raise BankStubServiceError("invalid_period")

    scope_key = make_stable_key(
        "bank_stub_statement",
        {"tenant_id": tenant_id, "period_from": period_from.isoformat(), "period_to": period_to.isoformat()},
        None,
    )
    lock_token = make_lock_token("bank_stub_statement", scope_key)
    with advisory_lock(db, lock_token) as acquired:
        if not acquired:
            raise BankStubServiceError("bank_stub_statement_locked")

        payments = (
            db.query(BankStubPayment)
            .filter(BankStubPayment.tenant_id == tenant_id)
            .filter(BankStubPayment.status.in_([BankStubPaymentStatus.POSTED, BankStubPaymentStatus.SETTLED]))
            .filter(BankStubPayment.created_at >= period_from)
            .filter(BankStubPayment.created_at <= period_to)
            .order_by(BankStubPayment.created_at.asc())
            .all()
        )
        currency = _extract_currency(payments)

        invoice_ids = {payment.invoice_id for payment in payments}
        invoice_numbers = {}
        if invoice_ids:
            invoices = db.query(BillingInvoice).filter(BillingInvoice.id.in_(invoice_ids)).all()
            invoice_numbers = {invoice.id: invoice.invoice_number for invoice in invoices}

        lines_payload: list[dict[str, object]] = []
        total_in = Decimal("0")
        for payment in payments:
            posted_at = payment.updated_at or payment.created_at
            line = {
                "payment_ref": payment.payment_ref,
                "invoice_number": invoice_numbers.get(payment.invoice_id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "posted_at": posted_at.isoformat(),
            }
            lines_payload.append(line)
            total_in += Decimal(payment.amount)

        payload = _statement_payload(
            period_from=period_from,
            period_to=period_to,
            currency=currency,
            lines=lines_payload,
            total_in=total_in,
        )
        checksum = _hash_payload(payload)

        existing = (
            db.query(BankStubStatement)
            .filter(BankStubStatement.tenant_id == tenant_id)
            .filter(BankStubStatement.checksum == checksum)
            .one_or_none()
        )
        if existing:
            return existing

        statement = BankStubStatement(
            tenant_id=tenant_id,
            period_from=period_from,
            period_to=period_to,
            payload=payload,
            checksum=checksum,
        )
        db.add(statement)
        db.flush()

        for payment, line_payload in zip(payments, lines_payload, strict=False):
            posted_at = datetime.fromisoformat(str(line_payload["posted_at"]))
            line = BankStubStatementLine(
                statement_id=statement.id,
                payment_ref=payment.payment_ref,
                invoice_number=line_payload.get("invoice_number"),
                amount=payment.amount,
                currency=payment.currency,
                posted_at=posted_at,
                meta={"bank_payment_id": str(payment.id)},
            )
            db.add(line)

        AuditService(db).audit(
            event_type="BANK_STUB_STATEMENT_GENERATED",
            entity_type="bank_stub_statement",
            entity_id=str(statement.id),
            action="generated",
            visibility=AuditVisibility.INTERNAL,
            after={
                "period_from": period_from.isoformat(),
                "period_to": period_to.isoformat(),
                "checksum": checksum,
                "lines": len(lines_payload),
            },
            request_ctx=actor,
        )

        return statement


def get_statement(db: Session, statement_id: str) -> BankStubStatement | None:
    _require_enabled()
    return db.query(BankStubStatement).filter(BankStubStatement.id == statement_id).one_or_none()


def build_statement_lines(statement: BankStubStatement) -> list[dict[str, object]]:
    lines = []
    for line in statement.lines:
        lines.append(
            {
                "payment_ref": line.payment_ref,
                "invoice_number": line.invoice_number,
                "amount": str(line.amount),
                "currency": line.currency,
                "posted_at": line.posted_at,
            }
        )
    return lines


def build_external_statement_payload(statement: BankStubStatement) -> dict[str, object]:
    lines = []
    total_in = Decimal("0")
    for line in statement.lines:
        line_payload = {
            "ref": line.payment_ref,
            "invoice_number": line.invoice_number,
            "amount": str(line.amount),
            "currency": line.currency,
            "timestamp": line.posted_at.isoformat(),
            "direction": "IN",
        }
        total_in += Decimal(line.amount)
        lines.append(line_payload)
    currency = None
    if statement.lines:
        currency = statement.lines[0].currency
    payload = _statement_payload(
        period_from=statement.period_from,
        period_to=statement.period_to,
        currency=currency,
        lines=lines,
        total_in=total_in,
    )
    payload["total_out"] = str(Decimal("0"))
    payload["closing_balance"] = str(total_in)
    return payload


def build_external_hash(statement: BankStubStatement) -> str:
    payload = build_external_statement_payload(statement)
    return _hash_payload(payload)


__all__ = [
    "BankStubServiceError",
    "build_external_hash",
    "build_external_statement_payload",
    "build_statement_lines",
    "create_stub_payment",
    "generate_statement",
    "get_statement",
    "get_stub_payment",
]
