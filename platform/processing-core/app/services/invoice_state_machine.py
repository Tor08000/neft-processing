from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Mapping

from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus, InvoiceTransitionLog
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.models.audit_log import ActorType
from app.services.audit_service import AuditService, RequestContext

logger = logging.getLogger(__name__)


class InvalidTransitionError(RuntimeError):
    """Raised when a lifecycle transition is not allowed."""


class InvoiceInvariantError(RuntimeError):
    """Raised when invoice financial invariants are violated."""


_ALLOWED_TRANSITIONS: Mapping[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: {InvoiceStatus.ISSUED},
    InvoiceStatus.ISSUED: {InvoiceStatus.SENT, InvoiceStatus.CANCELLED},
    InvoiceStatus.SENT: {
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.CANCELLED,
        InvoiceStatus.OVERDUE,
    },
    InvoiceStatus.PARTIALLY_PAID: {InvoiceStatus.PAID, InvoiceStatus.SENT},
    InvoiceStatus.PAID: {InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.SENT},
    InvoiceStatus.CANCELLED: set(),
    InvoiceStatus.OVERDUE: {InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID},
    InvoiceStatus.CREDITED: set(),
}


class InvoiceStateMachine:
    """Deterministic lifecycle controller for invoices."""

    def __init__(self, invoice: Invoice, *, db: Session, now_provider: Callable[[], datetime] | None = None):
        self.invoice = invoice
        self.db = db
        self._now_provider = now_provider or datetime.utcnow

    def _validate_allowed(self, target: InvoiceStatus) -> None:
        if target == self.invoice.status:
            return
        allowed = _ALLOWED_TRANSITIONS.get(self.invoice.status, set())
        if target not in allowed:
            raise InvalidTransitionError(f"transition {self.invoice.status} -> {target} is not allowed")

    def _apply_amounts(
        self,
        payment_amount: int | None,
        credit_note_amount: int | None,
        refund_amount: int | None,
    ) -> None:
        total = int(self.invoice.total_with_tax or self.invoice.total_amount or 0)
        paid = int(self.invoice.amount_paid or 0)
        credits = int(getattr(self.invoice, "credited_amount", 0) or 0)
        refunded = int(getattr(self.invoice, "amount_refunded", 0) or 0)

        if payment_amount is not None:
            if payment_amount < 0:
                raise InvoiceInvariantError("payment_amount must be non-negative")
            paid += int(payment_amount)
        if credit_note_amount is not None:
            if credit_note_amount < 0:
                raise InvoiceInvariantError("credit_note_amount must be non-negative")
            credits += int(credit_note_amount)
        if refund_amount is not None:
            if refund_amount < 0:
                raise InvoiceInvariantError("refund_amount must be non-negative")
            refunded += int(refund_amount)

        due = total - paid - credits + refunded
        if paid < 0 or credits < 0 or refunded < 0 or due < 0:
            raise InvoiceInvariantError("financial invariants violated")
        if paid + credits - refunded + due != total:
            raise InvoiceInvariantError("paid + credits - refunded + due must equal total")

        self.invoice.amount_paid = paid
        self.invoice.amount_due = due
        self.invoice.credited_amount = credits
        self.invoice.amount_refunded = refunded

    def _validate_constraints(
        self,
        target: InvoiceStatus,
        payment_amount: int | None,
        credit_note_amount: int | None,
        refund_amount: int | None,
    ) -> None:
        total = int(self.invoice.total_with_tax or self.invoice.total_amount or 0)
        paid = int(self.invoice.amount_paid or 0)
        credits = int(getattr(self.invoice, "credited_amount", 0) or 0)
        due = int(self.invoice.amount_due or 0)
        refunded = int(getattr(self.invoice, "amount_refunded", 0) or 0)

        if target == InvoiceStatus.CANCELLED:
            if paid > 0 or credits > 0 or refunded > 0:
                raise InvalidTransitionError("cannot cancel invoice with payments or credits")

        if target == InvoiceStatus.SENT and self.invoice.pdf_status != InvoicePdfStatus.READY:
            raise InvalidTransitionError("invoice pdf must be ready before sending")

        if target == InvoiceStatus.PARTIALLY_PAID:
            if paid <= 0 and (credit_note_amount is None or credit_note_amount <= 0):
                raise InvalidTransitionError("partial payment must be greater than zero")
            if (
                (payment_amount is None or payment_amount <= 0)
                and (refund_amount is None or refund_amount <= 0)
                and (credit_note_amount is None or credit_note_amount <= 0)
            ):
                raise InvalidTransitionError(
                    "payment, refund, or credit note amount required for partial payment"
                )
            if due < 0:
                raise InvalidTransitionError("partial payment cannot overpay invoice")

        if target == InvoiceStatus.PAID:
            if due != 0 or paid + credits - refunded != total:
                raise InvalidTransitionError("invoice must be fully settled before marking as paid")

        if target == InvoiceStatus.OVERDUE and due <= 0:
            raise InvalidTransitionError("cannot mark overdue when nothing is due")

    def _update_timestamps(self, target: InvoiceStatus, now: datetime) -> None:
        if target == InvoiceStatus.ISSUED and self.invoice.issued_at is None:
            self.invoice.issued_at = now
        if target == InvoiceStatus.SENT and self.invoice.sent_at is None:
            self.invoice.sent_at = now
        if target == InvoiceStatus.PAID and self.invoice.paid_at is None:
            self.invoice.paid_at = now
        if target == InvoiceStatus.CANCELLED and self.invoice.cancelled_at is None:
            self.invoice.cancelled_at = now
        if target == InvoiceStatus.CREDITED and self.invoice.credited_at is None:
            self.invoice.credited_at = now

    def _log_transition(self, from_status: InvoiceStatus, to_status: InvoiceStatus, *, actor: str, reason: str, metadata: Mapping[str, object] | None) -> None:
        log_entry = InvoiceTransitionLog(
            invoice_id=self.invoice.id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
            metadata_json=dict(metadata) if metadata else None,
        )
        self.db.add(log_entry)

    def transition(
        self,
        to: InvoiceStatus,
        *,
        actor: str,
        reason: str,
        payment_amount: int | None = None,
        credit_note_amount: int | None = None,
        refund_amount: int | None = None,
        metadata: Mapping[str, object] | None = None,
        request_ctx: RequestContext | None = None,
    ) -> Invoice:
        if not actor:
            raise ValueError("actor is required")
        if not reason:
            raise ValueError("reason is required")

        from_status = self.invoice.status
        if (
            to == from_status
            and not metadata
            and all(
                amount is None or amount == 0
                for amount in (payment_amount, credit_note_amount, refund_amount)
            )
        ):
            return self.invoice
        if self.invoice.billing_period_id:
            period = (
                self.db.query(BillingPeriod)
                .filter(BillingPeriod.id == self.invoice.billing_period_id)
                .one_or_none()
            )
            if period and period.status == BillingPeriodStatus.LOCKED:
                if reason != "financial_update" and (
                    to != self.invoice.status
                    or any(
                        amount is not None and amount != 0
                        for amount in (payment_amount, credit_note_amount, refund_amount)
                    )
                ):
                    raise InvalidTransitionError("billing period is locked")
        before_snapshot = {
            "status": from_status.value if from_status else None,
            "amount_paid": int(self.invoice.amount_paid or 0),
            "amount_due": int(self.invoice.amount_due or 0),
            "amount_refunded": int(getattr(self.invoice, "amount_refunded", 0) or 0),
            "credited_amount": int(getattr(self.invoice, "credited_amount", 0) or 0),
        }
        now = self._now_provider()

        self._validate_allowed(to)
        if to == InvoiceStatus.ISSUED:
            tenant_id = int(request_ctx.tenant_id) if request_ctx and request_ctx.tenant_id is not None else 0
            actor_type = "ADMIN" if request_ctx and request_ctx.actor_type == ActorType.USER else "SYSTEM"
            decision_context = DecisionContext(
                tenant_id=tenant_id,
                client_id=self.invoice.client_id,
                actor_type=actor_type,
                action=DecisionAction.INVOICE_ISSUE,
                amount=int(self.invoice.total_with_tax or self.invoice.total_amount or 0),
                currency=self.invoice.currency,
                invoice_id=self.invoice.id,
                billing_period_id=str(self.invoice.billing_period_id) if self.invoice.billing_period_id else None,
                history={},
                metadata={
                    "invoice_status": from_status.value if from_status else None,
                    "actor_roles": request_ctx.actor_roles if request_ctx else [],
                    "subject_id": self.invoice.id,
                },
            )
            decision = DecisionEngine(self.db).evaluate(decision_context)
            if decision.outcome != DecisionOutcome.ALLOW:
                raise InvalidTransitionError(f"DECISION_{decision.outcome.value}")
        self._apply_amounts(payment_amount, credit_note_amount, refund_amount)
        self._validate_constraints(to, payment_amount, credit_note_amount, refund_amount)
        self._update_timestamps(to, now)
        self.invoice.status = to

        self._log_transition(from_status, to, actor=actor, reason=reason, metadata=metadata)
        self.db.add(self.invoice)

        after_snapshot = {
            "status": self.invoice.status.value if self.invoice.status else None,
            "amount_paid": int(self.invoice.amount_paid or 0),
            "amount_due": int(self.invoice.amount_due or 0),
            "amount_refunded": int(getattr(self.invoice, "amount_refunded", 0) or 0),
            "credited_amount": int(getattr(self.invoice, "credited_amount", 0) or 0),
        }
        if hasattr(self.db, "query"):
            audit_ctx = request_ctx or RequestContext(actor_type=ActorType.SERVICE, actor_id=actor)
            AuditService(self.db).audit(
                event_type="INVOICE_STATUS_CHANGED",
                entity_type="invoice",
                entity_id=self.invoice.id,
                action="UPDATE_STATE",
                before=before_snapshot,
                after=after_snapshot,
                reason=reason,
                request_ctx=audit_ctx,
            )

        logger.info(
            "invoice.transition.applied",
            extra={
                "invoice_id": self.invoice.id,
                "from_status": from_status.value if from_status else None,
                "to_status": to.value if to else None,
                "actor": actor,
                "reason": reason,
                "metadata": metadata or {},
                "amount_paid": self.invoice.amount_paid,
                "amount_due": self.invoice.amount_due,
                "credited_amount": getattr(self.invoice, "credited_amount", 0),
                "amount_refunded": getattr(self.invoice, "amount_refunded", 0),
            },
        )
        return self.invoice


__all__ = ["InvoiceStateMachine", "InvalidTransitionError", "InvoiceInvariantError"]
