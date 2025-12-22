from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.billing_job_run import BillingJobStatus, BillingJobType
from app.models.finance import CreditNote, CreditNoteStatus, InvoicePayment, PaymentStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.services.billing_job_runs import BillingJobRunService
from app.services.job_locks import advisory_lock, make_lock_token
from app.services.invoice_state_machine import InvoiceStateMachine, InvalidTransitionError, InvoiceInvariantError


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

    def _lock_invoice(self, invoice_id: str) -> Invoice:
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        dialect = getattr(self.db.bind, "dialect", None)
        if dialect and dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        invoice = self.db.execute(stmt).scalar_one_or_none()
        if not invoice:
            raise InvoiceNotFound(invoice_id)
        return invoice

    def _apply_financial_transition(
        self,
        invoice: Invoice,
        *,
        target: InvoiceStatus,
        payment_amount: int | None = None,
        credit_note_amount: int | None = None,
    ) -> None:
        machine = InvoiceStateMachine(invoice, db=self.db)
        machine.transition(
            to=target,
            actor="finance_service",
            reason="financial_update",
            payment_amount=payment_amount,
            credit_note_amount=credit_note_amount,
            metadata={"source": "finance"},
        )

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
            current_paid = int(invoice.amount_paid or 0)
            current_credits = int(getattr(invoice, "credited_amount", 0) or 0)
            total = int(invoice.total_with_tax or invoice.total_amount or 0)
            new_total_paid = current_paid + amount
            outstanding = total - new_total_paid - current_credits
            target_status = InvoiceStatus.PARTIALLY_PAID if outstanding > 0 else InvoiceStatus.PAID

            try:
                self._apply_financial_transition(
                    invoice,
                    target=target_status,
                    payment_amount=amount,
                )
            except (InvalidTransitionError, InvoiceInvariantError):
                self.db.rollback()
                raise

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
            try:
                current_credits = int(getattr(invoice, "credited_amount", 0) or 0)
                current_paid = int(invoice.amount_paid or 0)
                total = int(invoice.total_with_tax or invoice.total_amount or 0)
                remaining_after_credit = total - current_paid - (current_credits + amount)
                self._apply_financial_transition(
                    invoice,
                    target=InvoiceStatus.CREDITED if remaining_after_credit <= 0 else InvoiceStatus.PARTIALLY_PAID,
                    credit_note_amount=amount,
                )
            except (InvalidTransitionError, InvoiceInvariantError):
                self.db.rollback()
                raise

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
