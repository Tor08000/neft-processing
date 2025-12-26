from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from app.models.billing_period import BillingPeriodStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ledger_entry import LedgerDirection


@dataclass(frozen=True)
class InvariantViolation:
    name: str
    expected: Any
    actual: Any


def _sum_by_currency(lines: Iterable[dict[str, Any]]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for line in lines:
        amount = Decimal(line["amount"])
        currency = str(line["currency"])
        direction = line["direction"]
        delta = amount if direction == LedgerDirection.CREDIT else -amount
        totals[currency] = totals.get(currency, Decimal("0")) + delta
    return totals


def validate_invoice(invoice: Invoice) -> list[InvariantViolation]:
    violations: list[InvariantViolation] = []
    total_amount = int(invoice.total_amount or 0)
    tax_amount = int(invoice.tax_amount or 0)
    total_with_tax = int(invoice.total_with_tax or 0)
    paid = int(invoice.amount_paid or 0)
    refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
    credited = int(getattr(invoice, "credited_amount", 0) or 0)
    due = int(invoice.amount_due or 0)

    expected_total_with_tax = total_amount + tax_amount
    if total_with_tax != expected_total_with_tax:
        violations.append(
            InvariantViolation(
                name="invoice.total_with_tax",
                expected=expected_total_with_tax,
                actual=total_with_tax,
            )
        )

    expected_due = expected_total_with_tax - paid - credited + refunded
    if due != expected_due:
        violations.append(
            InvariantViolation(
                name="invoice.amount_due",
                expected=expected_due,
                actual=due,
            )
        )

    if due < 0:
        violations.append(
            InvariantViolation(
                name="invoice.amount_due_non_negative",
                expected=">= 0",
                actual=due,
            )
        )
    if paid < 0:
        violations.append(
            InvariantViolation(
                name="invoice.amount_paid_non_negative",
                expected=">= 0",
                actual=paid,
            )
        )
    if refunded < 0:
        violations.append(
            InvariantViolation(
                name="invoice.amount_refunded_non_negative",
                expected=">= 0",
                actual=refunded,
            )
        )
    if credited < 0:
        violations.append(
            InvariantViolation(
                name="invoice.credited_amount_non_negative",
                expected=">= 0",
                actual=credited,
            )
        )

    expected_balance = paid + credited - refunded + due
    if expected_balance != expected_total_with_tax:
        violations.append(
            InvariantViolation(
                name="invoice.balance_equation",
                expected=expected_total_with_tax,
                actual={
                    "paid": paid,
                    "credited": credited,
                    "refunded": refunded,
                    "due": due,
                    "total_with_tax": total_with_tax,
                },
            )
        )

    return violations


def validate_payment_application(invoice: Invoice, *, amount: int) -> list[InvariantViolation]:
    violations: list[InvariantViolation] = []
    due = int(invoice.amount_due or 0)
    if amount < 0:
        violations.append(
            InvariantViolation(
                name="payment.amount_non_negative",
                expected=">= 0",
                actual=amount,
            )
        )
    if amount > due:
        violations.append(
            InvariantViolation(
                name="payment.amount_within_due",
                expected=f"<= {due}",
                actual=amount,
            )
        )
    if invoice.status in {InvoiceStatus.CANCELLED}:
        violations.append(
            InvariantViolation(
                name="payment.invoice_status",
                expected="not_cancelled",
                actual=invoice.status.value if invoice.status else None,
            )
        )
    return violations


def validate_refund(invoice: Invoice, *, amount: int) -> list[InvariantViolation]:
    violations: list[InvariantViolation] = []
    paid = int(invoice.amount_paid or 0)
    refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
    refundable = paid - refunded
    if amount < 0:
        violations.append(
            InvariantViolation(
                name="refund.amount_non_negative",
                expected=">= 0",
                actual=amount,
            )
        )
    if amount > refundable:
        violations.append(
            InvariantViolation(
                name="refund.amount_within_paid",
                expected=f"<= {refundable}",
                actual=amount,
            )
        )
    return violations


def validate_settlement_period(
    *,
    status: BillingPeriodStatus,
    override: bool,
) -> list[InvariantViolation]:
    if status == BillingPeriodStatus.LOCKED and not override:
        return [
            InvariantViolation(
                name="settlement.period_locked",
                expected="override",
                actual=status.value,
            )
        ]
    return []


def validate_settlement_total(*, total_allocated: int, invoice_total: int) -> list[InvariantViolation]:
    if total_allocated > invoice_total:
        return [
            InvariantViolation(
                name="settlement.allocations_total",
                expected=f"<= {invoice_total}",
                actual=total_allocated,
            )
        ]
    return []


def validate_ledger_lines(lines: Iterable[dict[str, Any]]) -> list[InvariantViolation]:
    violations: list[InvariantViolation] = []
    totals = _sum_by_currency(lines)
    for currency, delta in totals.items():
        if delta != Decimal("0"):
            violations.append(
                InvariantViolation(
                    name="ledger.double_entry",
                    expected="debit == credit",
                    actual={"currency": currency, "delta": str(delta)},
                )
            )
    return violations


__all__ = [
    "InvariantViolation",
    "validate_invoice",
    "validate_payment_application",
    "validate_refund",
    "validate_settlement_period",
    "validate_settlement_total",
    "validate_ledger_lines",
]
