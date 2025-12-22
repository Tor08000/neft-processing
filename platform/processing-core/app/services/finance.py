from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.billing_job_run import BillingJobStatus, BillingJobType
from app.models.finance import CreditNote, CreditNoteStatus, InvoicePayment, PaymentStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.services.billing_job_runs import BillingJobRunService
from app.services.job_locks import advisory_lock, make_lock_token
from app.services.invoice_state_machine import InvoiceStateMachine, InvoiceTransitionContext


class FinanceOperationInProgress(RuntimeError):
    """Finance operation already running for the requested invoice."""


class InvoiceNotFound(RuntimeError):
    """Invoice missing for finance operation."""


@dataclass
class PaymentResult:
    payment: InvoicePayment
    invoice: Invoice


@dataclass
class CreditNoteResult:
    credit_note: CreditNote
    invoice: Invoice


class FinanceService:
    """Handle finance operations (payments, credit notes) with idempotency."""

    def __init__(self, db: Session):
        self.db = db
        self.job_service = BillingJobRunService(db)
        self.state_machine = InvoiceStateMachine()

    def _lock_invoice(self, invoice_id: str) -> Invoice:
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        dialect = getattr(self.db.bind, "dialect", None)
        if dialect and dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        invoice = self.db.execute(stmt).scalar_one_or_none()
        if not invoice:
            raise InvoiceNotFound(invoice_id)
        return invoice

    def _recalculate_due(self, invoice: Invoice) -> None:
        payments_total = (
            self.db.query(func.coalesce(func.sum(InvoicePayment.amount), 0))
            .filter(InvoicePayment.invoice_id == invoice.id)
            .scalar()
        ) or 0
        credits_total = (
            self.db.query(func.coalesce(func.sum(CreditNote.amount), 0))
            .filter(CreditNote.invoice_id == invoice.id)
            .scalar()
        ) or 0

        invoice.amount_paid = int(payments_total)
        invoice.amount_due = max(
            int((invoice.total_with_tax or invoice.total_amount or 0) - payments_total - credits_total),
            0,
        )

        target_status = invoice.status
        if invoice.amount_due == 0 and invoice.status not in (InvoiceStatus.PAID, InvoiceStatus.VOIDED):
            target_status = InvoiceStatus.PAID
        elif invoice.amount_due > 0 and invoice.status not in (InvoiceStatus.VOIDED, InvoiceStatus.CANCELLED):
            target_status = InvoiceStatus.PARTIALLY_PAID

        context = InvoiceTransitionContext(
            actor="finance_service",
            reason="recalculate_due",
            payments_total=invoice.amount_paid,
            credits_total=int(credits_total),
        )
        self.state_machine.apply_transition(invoice, target_status, context=context)

        self.db.add(invoice)

    def apply_payment(
        self,
        *,
        invoice_id: str,
        amount: int,
        currency: str,
        idempotency_key: str,
    ) -> PaymentResult:
        existing = (
            self.db.query(InvoicePayment)
            .filter(InvoicePayment.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing:
            invoice = self._lock_invoice(invoice_id)
            return PaymentResult(payment=existing, invoice=invoice)

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        with txn_context:
            lock_token = make_lock_token("finance_payment", idempotency_key)
            with advisory_lock(self.db, lock_token) as acquired:
                if not acquired:
                    raise FinanceOperationInProgress(idempotency_key)

            invoice = self._lock_invoice(invoice_id)
            job_run = self.job_service.start(
                BillingJobType.FINANCE_PAYMENT,
                params={"invoice_id": invoice_id, "amount": amount, "currency": currency},
                correlation_id=idempotency_key,
                invoice_id=invoice_id,
            )
            payment = InvoicePayment(
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                idempotency_key=idempotency_key,
                status=PaymentStatus.POSTED,
            )
            self.db.add(payment)
            self._recalculate_due(invoice)

            self.job_service.succeed(
                job_run,
                metrics={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "due_amount": invoice.amount_due,
                },
                result_ref={
                    "invoice_id": invoice_id,
                    "payment_id": str(payment.id),
                    "due_amount": invoice.amount_due,
                },
            )
            return PaymentResult(payment=payment, invoice=invoice)

    def create_credit_note(
        self,
        *,
        invoice_id: str,
        amount: int,
        currency: str,
        reason: str | None,
        idempotency_key: str,
    ) -> CreditNoteResult:
        existing = (
            self.db.query(CreditNote)
            .filter(CreditNote.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing:
            invoice = self._lock_invoice(invoice_id)
            return CreditNoteResult(credit_note=existing, invoice=invoice)

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        with txn_context:
            lock_token = make_lock_token("finance_credit_note", idempotency_key)
            with advisory_lock(self.db, lock_token) as acquired:
                if not acquired:
                    raise FinanceOperationInProgress(idempotency_key)

            invoice = self._lock_invoice(invoice_id)
            job_run = self.job_service.start(
                BillingJobType.FINANCE_CREDIT_NOTE,
                params={"invoice_id": invoice_id, "amount": amount, "currency": currency, "reason": reason},
                correlation_id=idempotency_key,
                invoice_id=invoice_id,
            )

            credit_note = CreditNote(
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                reason=reason,
                idempotency_key=idempotency_key,
                status=CreditNoteStatus.POSTED,
            )
            self.db.add(credit_note)
            self._recalculate_due(invoice)

            self.job_service.succeed(
                job_run,
                metrics={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "due_amount": invoice.amount_due,
                },
                result_ref={
                    "invoice_id": invoice_id,
                    "credit_note_id": str(credit_note.id),
                    "due_amount": invoice.amount_due,
                },
            )
            return CreditNoteResult(credit_note=credit_note, invoice=invoice)
