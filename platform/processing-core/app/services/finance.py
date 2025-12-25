from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.billing_job_run import BillingJobStatus, BillingJobType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.finance import CreditNote, CreditNoteStatus, InvoicePayment, PaymentStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.services.billing_metrics import metrics as billing_metrics
from app.services.billing_job_runs import BillingJobRunService
from app.services.job_locks import advisory_lock, make_lock_token
from app.services.audit_service import RequestContext
from app.services.invoice_state_machine import InvoiceStateMachine, InvalidTransitionError, InvoiceInvariantError


class FinanceOperationInProgress(RuntimeError):
    """Finance operation already running for the requested invoice."""


class InvoiceNotFound(RuntimeError):
    """Invoice missing for finance operation."""


class PaymentReferenceConflict(RuntimeError):
    """Payment external reference points to a different invoice."""


class RefundReferenceConflict(RuntimeError):
    """Refund external reference points to a different invoice."""


@dataclass
class PaymentResult:
    payment: InvoicePayment
    invoice: Invoice
    is_replay: bool = False


@dataclass
class CreditNoteResult:
    credit_note: CreditNote
    invoice: Invoice
    is_replay: bool = False


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

    def _require_settlement_period(self, invoice: Invoice, *, action: str) -> None:
        if not invoice.billing_period_id:
            return
        period = (
            self.db.query(BillingPeriod)
            .filter(BillingPeriod.id == invoice.billing_period_id)
            .one_or_none()
        )
        if not period:
            raise InvalidTransitionError("billing period not found")
        if period.status != BillingPeriodStatus.FINALIZED:
            raise InvalidTransitionError(f"billing period {period.id} is {period.status.value} for {action}")

    def _apply_financial_transition(
        self,
        invoice: Invoice,
        *,
        target: InvoiceStatus,
        payment_amount: int | None = None,
        credit_note_amount: int | None = None,
        refund_amount: int | None = None,
        request_ctx: RequestContext | None = None,
    ) -> None:
        machine = InvoiceStateMachine(invoice, db=self.db)
        machine.transition(
            to=target,
            actor="finance_service",
            reason="financial_update",
            payment_amount=payment_amount,
            credit_note_amount=credit_note_amount,
            refund_amount=refund_amount,
            metadata={"source": "finance"},
            request_ctx=request_ctx,
        )

    def apply_payment(
        self,
        *,
        invoice_id: str,
        amount: int,
        currency: str,
        idempotency_key: str,
        external_ref: str | None = None,
        provider: str | None = None,
        request_ctx: RequestContext | None = None,
    ) -> PaymentResult:
        try:
            if external_ref:
                query = self.db.query(InvoicePayment).filter(InvoicePayment.external_ref == external_ref)
                if provider is None:
                    query = query.filter(InvoicePayment.provider.is_(None))
                else:
                    query = query.filter(InvoicePayment.provider == provider)
                existing_by_ref = query.one_or_none()
                if existing_by_ref:
                    if existing_by_ref.invoice_id != invoice_id:
                        billing_metrics.mark_payment_error()
                        billing_metrics.mark_payment_failed()
                        raise PaymentReferenceConflict(external_ref)
                    invoice = self._lock_invoice(invoice_id)
                    return PaymentResult(payment=existing_by_ref, invoice=invoice, is_replay=True)
        except InvoiceNotFound:
            billing_metrics.mark_payment_error()
            billing_metrics.mark_payment_failed()
            raise

        existing = (
            self.db.query(InvoicePayment)
            .filter(InvoicePayment.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing:
            invoice = self._lock_invoice(invoice_id)
            return PaymentResult(payment=existing, invoice=invoice, is_replay=True)

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        with txn_context:
            lock_token = make_lock_token("finance_payment", idempotency_key)
            with advisory_lock(self.db, lock_token) as acquired:
                if not acquired:
                    billing_metrics.mark_payment_failed()
                    raise FinanceOperationInProgress(idempotency_key)

            invoice = self._lock_invoice(invoice_id)
            self._require_settlement_period(invoice, action="payment")
            job_run = self.job_service.start(
                BillingJobType.FINANCE_PAYMENT,
                params={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "external_ref": external_ref,
                    "provider": provider,
                },
                correlation_id=idempotency_key,
                invoice_id=invoice_id,
            )
            payment = InvoicePayment(
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                idempotency_key=idempotency_key,
                external_ref=external_ref,
                provider=provider,
                status=PaymentStatus.POSTED,
            )
            self.db.add(payment)
            current_paid = int(invoice.amount_paid or 0)
            current_credits = int(getattr(invoice, "credited_amount", 0) or 0)
            current_refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
            total = int(invoice.total_with_tax or invoice.total_amount or 0)
            outstanding_before = total - current_paid - current_credits + current_refunded

            if invoice.status not in {InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID}:
                self.db.rollback()
                billing_metrics.mark_payment_error()
                raise InvalidTransitionError(f"payments allowed only from sent/partial, got {invoice.status}")

            try:
                if amount > outstanding_before:
                    raise InvoiceInvariantError("payment exceeds outstanding balance")

                target_status = InvoiceStatus.PARTIALLY_PAID
                if amount >= outstanding_before:
                    target_status = InvoiceStatus.PAID

                self._apply_financial_transition(
                    invoice,
                    target=target_status,
                    payment_amount=amount,
                    request_ctx=request_ctx,
                )
            except (InvalidTransitionError, InvoiceInvariantError):
                self.db.rollback()
                billing_metrics.mark_payment_error()
                billing_metrics.mark_payment_failed()
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
            billing_metrics.mark_payment_posted()
            billing_metrics.mark_payment_amount(amount)
            if invoice.status == InvoiceStatus.PAID:
                billing_metrics.mark_invoice_paid()
            return PaymentResult(payment=payment, invoice=invoice, is_replay=False)

    def create_credit_note(
        self,
        *,
        invoice_id: str,
        amount: int,
        currency: str,
        reason: str | None,
        idempotency_key: str,
        request_ctx: RequestContext | None = None,
    ) -> CreditNoteResult:
        existing = (
            self.db.query(CreditNote)
            .filter(CreditNote.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing:
            invoice = self._lock_invoice(invoice_id)
            return CreditNoteResult(credit_note=existing, invoice=invoice, is_replay=True)

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        with txn_context:
            lock_token = make_lock_token("finance_credit_note", idempotency_key)
            with advisory_lock(self.db, lock_token) as acquired:
                if not acquired:
                    raise FinanceOperationInProgress(idempotency_key)

            invoice = self._lock_invoice(invoice_id)
            self._require_settlement_period(invoice, action="credit_note")
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
                current_refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
                current_paid = int(invoice.amount_paid or 0)
                total = int(invoice.total_with_tax or invoice.total_amount or 0)
                remaining_after_credit = total - current_paid - (current_credits + amount) + current_refunded
                if invoice.status not in {InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID}:
                    self.db.rollback()
                    raise InvalidTransitionError(f"credit notes allowed only from sent/partial, got {invoice.status}")

                if invoice.status == InvoiceStatus.SENT:
                    self._apply_financial_transition(
                        invoice,
                        target=InvoiceStatus.PARTIALLY_PAID,
                        credit_note_amount=amount,
                        request_ctx=request_ctx,
                    )
                    if invoice.amount_due <= 0:
                        self._apply_financial_transition(
                            invoice,
                            target=InvoiceStatus.PAID,
                            request_ctx=request_ctx,
                        )
                else:
                    target_status = InvoiceStatus.PARTIALLY_PAID
                    if remaining_after_credit <= 0:
                        target_status = InvoiceStatus.PAID

                    self._apply_financial_transition(
                        invoice,
                        target=target_status,
                        credit_note_amount=amount,
                        request_ctx=request_ctx,
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
            return CreditNoteResult(credit_note=credit_note, invoice=invoice, is_replay=False)

    def create_refund(
        self,
        *,
        invoice_id: str,
        amount: int,
        currency: str,
        reason: str | None,
        external_ref: str | None,
        provider: str | None,
        request_ctx: RequestContext | None = None,
    ) -> CreditNoteResult:
        if external_ref:
            existing_by_ref = (
                self.db.query(CreditNote)
                .filter(CreditNote.external_ref == external_ref)
                .filter(CreditNote.provider == provider)
                .one_or_none()
            )
            if existing_by_ref:
                if existing_by_ref.invoice_id != invoice_id:
                    raise RefundReferenceConflict(external_ref)
                invoice = self._lock_invoice(invoice_id)
                return CreditNoteResult(credit_note=existing_by_ref, invoice=invoice, is_replay=True)

        txn_context = nullcontext() if self.db.in_transaction() else self.db.begin()
        job_run = None

        with txn_context:
            lock_token = make_lock_token("finance_refund", external_ref or f"{invoice_id}:{amount}")
            with advisory_lock(self.db, lock_token) as acquired:
                if not acquired:
                    billing_metrics.mark_payment_error()

            invoice = self._lock_invoice(invoice_id)
            self._require_settlement_period(invoice, action="refund")
            if invoice.status not in {InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID}:
                self.db.rollback()
                raise InvalidTransitionError(
                    f"refunds allowed only from paid/partial, got {invoice.status}"
                )

            job_run = self.job_service.start(
                BillingJobType.FINANCE_CREDIT_NOTE,
                params={
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "currency": currency,
                    "reason": reason,
                    "external_ref": external_ref,
                    "provider": provider,
                },
                correlation_id=external_ref or f"refund:{invoice_id}",
                invoice_id=invoice_id,
            )

            refund = CreditNote(
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                reason=reason,
                idempotency_key=external_ref or f"refund:{invoice_id}:{amount}",
                external_ref=external_ref,
                provider=provider,
                status=CreditNoteStatus.POSTED,
            )
            self.db.add(refund)

            try:
                current_paid = int(invoice.amount_paid or 0)
                current_refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
                refundable = current_paid - current_refunded
                if amount > refundable:
                    raise InvoiceInvariantError("refund exceeds paid amount")

                net_paid_after = current_paid - (current_refunded + amount)
                target_status = InvoiceStatus.PARTIALLY_PAID
                if net_paid_after <= 0:
                    target_status = InvoiceStatus.SENT

                self._apply_financial_transition(
                    invoice,
                    target=target_status,
                    refund_amount=amount,
                    request_ctx=request_ctx,
                )
                self.db.flush()
            except IntegrityError:
                self.db.rollback()
                if external_ref:
                    existing = (
                        self.db.query(CreditNote)
                        .filter(CreditNote.external_ref == external_ref)
                        .filter(CreditNote.provider == provider)
                        .one_or_none()
                    )
                    if existing:
                        invoice = self._lock_invoice(invoice_id)
                        return CreditNoteResult(credit_note=existing, invoice=invoice, is_replay=True)
                raise
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
                    "credit_note_id": str(refund.id),
                    "due_amount": invoice.amount_due,
                },
            )
            billing_metrics.mark_refund_posted()
            return CreditNoteResult(credit_note=refund, invoice=invoice, is_replay=False)
