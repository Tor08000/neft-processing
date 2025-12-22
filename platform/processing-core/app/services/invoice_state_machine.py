from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from fastapi import HTTPException, status

from app.models.invoice import Invoice, InvoiceStatus

logger = logging.getLogger(__name__)


@dataclass
class InvoiceTransitionContext:
    actor: str | None
    reason: str | None
    allow_cancel_paid: bool = False
    skip_timestamp_update: bool = False
    payments_total: int | None = None
    credits_total: int | None = None


class InvoiceStateMachine:
    """Centralized guard for invoice lifecycle transitions."""

    def __init__(self, now_provider: Callable[[], datetime] | None = None):
        self._now_provider = now_provider or datetime.utcnow

    def _status_exists(self, status: InvoiceStatus) -> bool:
        return status.name in InvoiceStatus.__members__

    def _allowed_transitions(self) -> dict[InvoiceStatus, set[InvoiceStatus]]:
        allowed: dict[InvoiceStatus, set[InvoiceStatus]] = {}

        if self._status_exists(InvoiceStatus.DRAFT):
            allowed[InvoiceStatus.DRAFT] = set()
            if self._status_exists(InvoiceStatus.ISSUED):
                allowed[InvoiceStatus.DRAFT].add(InvoiceStatus.ISSUED)
            if self._status_exists(InvoiceStatus.CANCELLED):
                allowed[InvoiceStatus.DRAFT].add(InvoiceStatus.CANCELLED)

        if self._status_exists(InvoiceStatus.ISSUED):
            allowed[InvoiceStatus.ISSUED] = set()
            if self._status_exists(InvoiceStatus.SENT):
                allowed[InvoiceStatus.ISSUED].add(InvoiceStatus.SENT)
            if self._status_exists(InvoiceStatus.CANCELLED):
                allowed[InvoiceStatus.ISSUED].add(InvoiceStatus.CANCELLED)

        if self._status_exists(InvoiceStatus.SENT):
            allowed[InvoiceStatus.SENT] = set()
            if self._status_exists(InvoiceStatus.PARTIALLY_PAID):
                allowed[InvoiceStatus.SENT].add(InvoiceStatus.PARTIALLY_PAID)
            if self._status_exists(InvoiceStatus.PAID):
                allowed[InvoiceStatus.SENT].add(InvoiceStatus.PAID)
            if self._status_exists(InvoiceStatus.CANCELLED):
                allowed[InvoiceStatus.SENT].add(InvoiceStatus.CANCELLED)
            if self._status_exists(InvoiceStatus.DELIVERED):
                allowed[InvoiceStatus.SENT].add(InvoiceStatus.DELIVERED)

        if self._status_exists(InvoiceStatus.PARTIALLY_PAID):
            allowed[InvoiceStatus.PARTIALLY_PAID] = set()
            if self._status_exists(InvoiceStatus.PAID):
                allowed[InvoiceStatus.PARTIALLY_PAID].add(InvoiceStatus.PAID)
            if self._status_exists(InvoiceStatus.DELIVERED):
                allowed[InvoiceStatus.PARTIALLY_PAID].add(InvoiceStatus.DELIVERED)

        if self._status_exists(InvoiceStatus.PAID):
            allowed[InvoiceStatus.PAID] = set()
            if self._status_exists(InvoiceStatus.DELIVERED):
                allowed[InvoiceStatus.PAID].add(InvoiceStatus.DELIVERED)

        if self._status_exists(InvoiceStatus.DELIVERED):
            allowed[InvoiceStatus.DELIVERED] = set()

        if self._status_exists(InvoiceStatus.CANCELLED):
            allowed[InvoiceStatus.CANCELLED] = set()

        if self._status_exists(InvoiceStatus.VOIDED):
            allowed[InvoiceStatus.VOIDED] = set()

        return allowed

    def _resolve_amounts(self, invoice: Invoice, context: InvoiceTransitionContext) -> tuple[int, int, int]:
        payments_total = context.payments_total if context.payments_total is not None else (invoice.amount_paid or 0)
        credits_total = context.credits_total if context.credits_total is not None else 0
        total_due = invoice.total_with_tax or invoice.total_amount or 0

        if payments_total < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payments_total must be non-negative")
        if credits_total < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="credits_total must be non-negative")

        return int(payments_total), int(credits_total), int(total_due)

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
                "denial_reason": reason,
            },
        )

    def validate_transition(
        self,
        invoice: Invoice,
        target_status: InvoiceStatus,
        *,
        context: InvoiceTransitionContext,
    ) -> None:
        payments_total, credits_total, total_due = self._resolve_amounts(invoice, context)

        if invoice.status == target_status:
            return

        allowed = self._allowed_transitions().get(invoice.status, set())
        if target_status not in allowed:
            self._log_denied(invoice, target_status, context=context, reason="transition_not_allowed")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"transition {invoice.status} -> {target_status} is not allowed",
            )

        has_payments_or_credits = payments_total > 0 or credits_total > 0
        if target_status == InvoiceStatus.CANCELLED and has_payments_or_credits and not context.allow_cancel_paid:
            self._log_denied(invoice, target_status, context=context, reason="payments_or_credits_present")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot cancel invoice with payments or credits",
            )

        outstanding_without_payments = max(total_due - credits_total, 0)
        if target_status == InvoiceStatus.PAID and payments_total < outstanding_without_payments:
            self._log_denied(invoice, target_status, context=context, reason="insufficient_payment_for_paid")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="invoice cannot be marked paid while amount is still due",
            )

        if target_status == InvoiceStatus.PARTIALLY_PAID:
            if payments_total <= 0 or payments_total >= outstanding_without_payments:
                self._log_denied(invoice, target_status, context=context, reason="invalid_partial_payment_amount")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="partial payment must be greater than zero and less than amount due",
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
        return updated

    def _normalize_amounts(self, invoice: Invoice, context: InvoiceTransitionContext) -> None:
        payments_total, credits_total, total_due = self._resolve_amounts(invoice, context)
        invoice.amount_paid = payments_total
        invoice.amount_due = max(total_due - payments_total - credits_total, 0)

    def apply_transition(
        self,
        invoice: Invoice,
        target_status: InvoiceStatus,
        *,
        now: datetime | None = None,
        context: InvoiceTransitionContext,
    ) -> Invoice:
        self.validate_transition(invoice, target_status, context=context)

        resolved_now = now or self._now_provider()
        previous_status = invoice.status
        timestamp_fields = self._apply_timestamps(invoice, target_status, now=resolved_now, context=context)

        if invoice.status != target_status:
            invoice.status = target_status

        self._normalize_amounts(invoice, context)

        logger.info(
            "invoice.transition.applied",
            extra={
                "invoice_id": invoice.id,
                "from_status": previous_status.value if previous_status else None,
                "to_status": target_status.value if target_status else None,
                "actor": context.actor,
                "reason": context.reason,
                "timestamp_fields": timestamp_fields,
                "amount_due": invoice.amount_due,
                "amount_paid": invoice.amount_paid,
            },
        )
        return invoice


__all__ = ["InvoiceStateMachine", "InvoiceTransitionContext"]
