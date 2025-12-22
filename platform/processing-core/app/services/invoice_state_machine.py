from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping

from fastapi import HTTPException, status

from app.models.invoice import Invoice, InvoiceStatus

logger = logging.getLogger(__name__)


@dataclass
class InvoiceTransitionContext:
    actor: str | None
    reason: str | None
    source: str | None = None
    correlation_id: str | None = None
    metadata: Mapping[str, object] | None = None
    allow_cancel_paid: bool = False
    allow_terminal_reopen: bool = False
    skip_timestamp_update: bool = False
    payments_total: int | None = None
    credits_total: int | None = None


@dataclass
class InvoiceFinancials:
    payments_total: int
    credits_total: int
    total_due: int
    amount_due: int


TERMINAL_STATUSES = {
    InvoiceStatus.CANCELLED,
    InvoiceStatus.VOIDED,
    InvoiceStatus.REFUNDED,
    InvoiceStatus.CLOSED,
}


class InvoiceStateMachine:
    """Centralized guard for invoice lifecycle transitions."""

    def __init__(self, now_provider: Callable[[], datetime] | None = None):
        self._now_provider = now_provider or datetime.utcnow

    def _allowed_transitions(self) -> dict[InvoiceStatus, set[InvoiceStatus]]:
        return {
            InvoiceStatus.DRAFT: {InvoiceStatus.ISSUED, InvoiceStatus.CANCELLED},
            InvoiceStatus.ISSUED: {
                InvoiceStatus.SENT,
                InvoiceStatus.CANCELLED,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.PAID,
            },
            InvoiceStatus.SENT: {
                InvoiceStatus.DELIVERED,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.PAID,
                InvoiceStatus.CANCELLED,
            },
            InvoiceStatus.DELIVERED: {InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID},
            InvoiceStatus.PARTIALLY_PAID: {InvoiceStatus.PAID, InvoiceStatus.DELIVERED},
            InvoiceStatus.PAID: {InvoiceStatus.CLOSED, InvoiceStatus.DELIVERED, InvoiceStatus.REFUNDED},
            InvoiceStatus.CANCELLED: set(),
            InvoiceStatus.VOIDED: set(),
            InvoiceStatus.REFUNDED: set(),
            InvoiceStatus.CLOSED: set(),
        }

    def _resolve_amounts(self, invoice: Invoice, context: InvoiceTransitionContext) -> InvoiceFinancials:
        payments_total = int(context.payments_total if context.payments_total is not None else (invoice.amount_paid or 0))
        credits_total = int(context.credits_total if context.credits_total is not None else 0)
        total_due = int(invoice.total_with_tax or invoice.total_amount or 0)

        if payments_total < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payments_total must be non-negative")
        if credits_total < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="credits_total must be non-negative")

        amount_due = max(total_due - payments_total - credits_total, 0)
        return InvoiceFinancials(
            payments_total=payments_total,
            credits_total=credits_total,
            total_due=total_due,
            amount_due=amount_due,
        )

    def _derive_financial_status(
        self, invoice: Invoice, target_status: InvoiceStatus, *, amounts: InvoiceFinancials
    ) -> InvoiceStatus:
        if target_status in TERMINAL_STATUSES:
            return target_status

        if amounts.amount_due == 0:
            return InvoiceStatus.PAID
        if amounts.payments_total > 0 and amounts.amount_due < amounts.total_due:
            return InvoiceStatus.PARTIALLY_PAID
        return target_status

    def _log_denied(
        self,
        invoice: Invoice,
        target_status: InvoiceStatus,
        *,
        context: InvoiceTransitionContext,
        reason: str,
    ) -> None:
        logger.info(
            "invoice.transition.denied",
            extra={
                "invoice_id": invoice.id,
                "status": invoice.status.value if invoice.status else None,
                "target_status": target_status.value if target_status else None,
                "actor": context.actor,
                "reason": context.reason,
                "source": context.source,
                "correlation_id": context.correlation_id,
                "metadata": context.metadata or {},
                "payments_total": context.payments_total,
                "credits_total": context.credits_total,
                "denial_reason": reason,
            },
        )

    def _validate_transition(
        self,
        invoice: Invoice,
        requested_status: InvoiceStatus,
        final_status: InvoiceStatus,
        *,
        context: InvoiceTransitionContext,
        amounts: InvoiceFinancials,
    ) -> None:
        if invoice.status in TERMINAL_STATUSES and final_status != invoice.status and not context.allow_terminal_reopen:
            self._log_denied(invoice, requested_status, context=context, reason="terminal_status")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"cannot transition from terminal status {invoice.status}",
            )

        if invoice.status == requested_status:
            return

        allowed = self._allowed_transitions().get(invoice.status, set())
        if requested_status not in allowed:
            self._log_denied(invoice, requested_status, context=context, reason="transition_not_allowed")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"transition {invoice.status} -> {requested_status} is not allowed",
            )
        if final_status not in allowed and final_status != invoice.status:
            self._log_denied(invoice, final_status, context=context, reason="transition_not_allowed")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"transition {invoice.status} -> {final_status} is not allowed",
            )

        has_payments_or_credits = amounts.payments_total > 0 or amounts.credits_total > 0
        if final_status == InvoiceStatus.CANCELLED and has_payments_or_credits and not context.allow_cancel_paid:
            self._log_denied(invoice, final_status, context=context, reason="payments_or_credits_present")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot cancel invoice with payments or credits",
            )

        outstanding_without_payments = max(amounts.total_due - amounts.credits_total, 0)
        if final_status == InvoiceStatus.PAID and amounts.payments_total < outstanding_without_payments:
            self._log_denied(invoice, final_status, context=context, reason="insufficient_payment_for_paid")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="invoice cannot be marked paid while amount is still due",
            )

        if final_status == InvoiceStatus.PARTIALLY_PAID:
            if amounts.payments_total <= 0 or amounts.payments_total >= outstanding_without_payments:
                self._log_denied(invoice, final_status, context=context, reason="invalid_partial_payment_amount")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="partial payment must be greater than zero and less than amount due",
                )

        if final_status == InvoiceStatus.CLOSED and invoice.status != InvoiceStatus.PAID:
            self._log_denied(invoice, final_status, context=context, reason="close_requires_paid")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="invoice must be paid before closing",
            )

    def _apply_timestamps(
        self,
        invoice: Invoice,
        target_status: InvoiceStatus,
        *,
        now: datetime,
        context: InvoiceTransitionContext,
    ) -> list[str]:
        updated: list[str] = []
        if context.skip_timestamp_update:
            return updated

        if target_status == InvoiceStatus.ISSUED and invoice.issued_at is None:
            invoice.issued_at = now
            updated.append("issued_at")
        if target_status == InvoiceStatus.SENT and invoice.sent_at is None:
            invoice.sent_at = now
            updated.append("sent_at")
        if target_status == InvoiceStatus.DELIVERED and invoice.delivered_at is None:
            invoice.delivered_at = now
            updated.append("delivered_at")
        if target_status == InvoiceStatus.PAID and invoice.paid_at is None:
            invoice.paid_at = now
            updated.append("paid_at")
        if target_status == InvoiceStatus.CANCELLED and invoice.cancelled_at is None:
            invoice.cancelled_at = now
            updated.append("cancelled_at")
        if target_status == InvoiceStatus.CLOSED and invoice.closed_at is None:
            invoice.closed_at = now
            updated.append("closed_at")
        if target_status == InvoiceStatus.REFUNDED and invoice.refunded_at is None:
            invoice.refunded_at = now
            updated.append("refunded_at")
        return updated

    def _normalize_amounts(self, invoice: Invoice, context: InvoiceTransitionContext) -> InvoiceFinancials:
        amounts = self._resolve_amounts(invoice, context)
        invoice.amount_paid = amounts.payments_total
        invoice.amount_due = amounts.amount_due
        return amounts

    def normalize_financials(
        self, invoice: Invoice, *, context: InvoiceTransitionContext, update_status: bool = True
    ) -> InvoiceStatus:
        """Normalize paid/due amounts and optionally align lifecycle with payments and credits."""

        amounts = self._normalize_amounts(invoice, context)
        derived_status = self._derive_financial_status(invoice, invoice.status, amounts=amounts)
        if update_status and invoice.status not in TERMINAL_STATUSES and derived_status != invoice.status:
            invoice.status = derived_status
        return derived_status

    def apply_transition(
        self,
        invoice: Invoice,
        target_status: InvoiceStatus,
        *,
        now: datetime | None = None,
        context: InvoiceTransitionContext,
    ) -> Invoice:
        resolved_now = now or self._now_provider()
        amounts = self._normalize_amounts(invoice, context)
        final_status = self._derive_financial_status(invoice, target_status, amounts=amounts)

        if target_status == InvoiceStatus.PAID and final_status != InvoiceStatus.PAID:
            self._log_denied(invoice, target_status, context=context, reason="insufficient_payment_for_paid")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="invoice cannot be marked paid while amount is still due",
            )
        if target_status == InvoiceStatus.PARTIALLY_PAID and final_status != InvoiceStatus.PARTIALLY_PAID:
            self._log_denied(invoice, target_status, context=context, reason="invalid_partial_payment_amount")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="partial payment must be greater than zero and less than amount due",
            )

        self._validate_transition(
            invoice,
            target_status,
            final_status,
            context=context,
            amounts=amounts,
        )

        previous_status = invoice.status
        timestamp_fields = self._apply_timestamps(invoice, final_status, now=resolved_now, context=context)

        if invoice.status != final_status:
            invoice.status = final_status

        logger.info(
            "invoice.transition.applied",
            extra={
                "invoice_id": invoice.id,
                "from_status": previous_status.value if previous_status else None,
                "to_status": final_status.value if final_status else None,
                "actor": context.actor,
                "reason": context.reason,
                "source": context.source,
                "correlation_id": context.correlation_id,
                "metadata": context.metadata or {},
                "timestamp_fields": timestamp_fields,
                "amount_due": invoice.amount_due,
                "amount_paid": invoice.amount_paid,
            },
        )
        return invoice


__all__ = ["InvoiceStateMachine", "InvoiceTransitionContext"]
