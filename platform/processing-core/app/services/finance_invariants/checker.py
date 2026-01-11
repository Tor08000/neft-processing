from __future__ import annotations

from dataclasses import asdict
import os
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit_log import AuditVisibility
from app.models.billing_period import BillingPeriod
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice
from app.services.audit_service import AuditService, RequestContext
from app.services.finance_invariants.errors import FinancialInvariantViolation
from app.services.finance_invariants import rules


class FinancialInvariantChecker:
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    def _build_error(
        self,
        *,
        entity_type: str,
        entity_id: str,
        violations: list[rules.InvariantViolation],
        ledger_transaction_id: str | None = None,
        context: dict | None = None,
    ) -> FinancialInvariantViolation:
        primary = violations[0]
        return FinancialInvariantViolation(
            entity_type=entity_type,
            entity_id=str(entity_id),
            invariant_name=primary.name,
            expected=primary.expected,
            actual=primary.actual,
            ledger_transaction_id=ledger_transaction_id,
            violations=violations,
            context=context,
        )

    def audit_violation(
        self,
        violation: FinancialInvariantViolation,
        *,
        request_ctx: RequestContext | None = None,
        extra_payload: dict | None = None,
    ) -> None:
        payload = {
            "entity": violation.entity_type,
            "invariants": [
                asdict(item) if not isinstance(item, dict) else item
                for item in (violation.violations or [])
            ]
            or [
                {
                    "name": violation.invariant_name,
                    "expected": violation.expected,
                    "actual": violation.actual,
                }
            ],
            "ledger_transaction_id": violation.ledger_transaction_id,
        }
        if violation.context:
            payload["context"] = violation.context
        if extra_payload:
            payload.update(extra_payload)
        self.audit_service.audit(
            event_type="FINANCIAL_INVARIANT_VIOLATION",
            entity_type=violation.entity_type,
            entity_id=str(violation.entity_id),
            action="VALIDATE",
            visibility=AuditVisibility.INTERNAL,
            after=payload,
            request_ctx=request_ctx,
            reason=violation.invariant_name,
        )

    def _invoice_snapshot(self, invoice: Invoice) -> dict[str, object]:
        total = int(invoice.total_with_tax or invoice.total_amount or 0)
        total_amount = int(invoice.total_amount or 0)
        total_with_tax = int(invoice.total_with_tax or 0)
        paid = int(invoice.amount_paid or 0)
        refunded = int(getattr(invoice, "amount_refunded", 0) or 0)
        credited = int(getattr(invoice, "credited_amount", 0) or 0)
        due = int(invoice.amount_due or 0)
        allocations = (
            self.db.query(InvoiceSettlementAllocation)
            .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
            .all()
        )
        summary = {
            "count": len(allocations),
            "total_payments": 0,
            "total_credits": 0,
            "total_refunds": 0,
            "settlement_period_ids": sorted(
                {str(allocation.settlement_period_id) for allocation in allocations}
            ),
        }
        for allocation in allocations:
            if allocation.source_type == SettlementSourceType.PAYMENT:
                summary["total_payments"] += int(allocation.amount or 0)
            elif allocation.source_type == SettlementSourceType.CREDIT_NOTE:
                summary["total_credits"] += int(allocation.amount or 0)
            elif allocation.source_type == SettlementSourceType.REFUND:
                summary["total_refunds"] += int(allocation.amount or 0)

        return {
            "invoice_id": str(invoice.id),
            "billing_period_id": str(invoice.billing_period_id) if invoice.billing_period_id else None,
            "currency": invoice.currency,
            "total": total,
            "total_amount": total_amount,
            "total_with_tax": total_with_tax,
            "paid": paid,
            "refunded": refunded,
            "credited": credited,
            "due": due,
            "allocations": summary,
        }

    @staticmethod
    def _is_test_mode() -> bool:
        return bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_XDIST_WORKER"))

    def _settlement_debug_snapshot(
        self,
        *,
        invoice: Invoice,
        allocations: list[InvoiceSettlementAllocation],
        total_payments: int,
        total_credits: int,
        total_refunds: int,
    ) -> dict[str, object]:
        paid_total = int(
            self.db.query(func.coalesce(func.sum(InvoicePayment.amount), 0))
            .filter(InvoicePayment.invoice_id == invoice.id)
            .scalar()
            or 0
        )
        refund_total = int(getattr(invoice, "amount_refunded", 0) or 0)
        credited_total = int(getattr(invoice, "credited_amount", 0) or 0)
        penalty_total = int(
            self.db.query(func.coalesce(func.sum(CreditNote.amount), 0))
            .filter(CreditNote.invoice_id == invoice.id)
            .filter(CreditNote.reason == "sla_penalty")
            .scalar()
            or 0
        )
        allocation_lines = []
        for allocation in allocations:
            allocation_lines.append(
                {
                    "id": str(allocation.id),
                    "invoice_id": str(allocation.invoice_id),
                    "source_type": allocation.source_type.value if allocation.source_type else None,
                    "source_id": allocation.source_id,
                    "amount_allocated": int(allocation.amount or 0),
                    "amount_released": (
                        allocation.meta.get("amount_released") if isinstance(allocation.meta, dict) else None
                    ),
                    "amount_refunded": (
                        allocation.meta.get("amount_refunded") if isinstance(allocation.meta, dict) else None
                    ),
                    "created_at": allocation.applied_at,
                }
            )
        alloc_total = int(sum(int(allocation.amount or 0) for allocation in allocations))
        alloc_net = int(total_payments - total_credits - total_refunds)
        return {
            "invoice_id": str(invoice.id),
            "total_amount": int(invoice.total_amount or 0),
            "amount_paid": int(invoice.amount_paid or 0),
            "amount_due": int(invoice.amount_due or 0),
            "amount_refunded": refund_total,
            "credited_amount": credited_total,
            "currency": invoice.currency,
            "allocations": allocation_lines,
            "allocation_totals": {
                "alloc_total": alloc_total,
                "alloc_net": alloc_net,
                "total_payments": total_payments,
                "total_credits": total_credits,
                "total_refunds": total_refunds,
            },
            "computed_totals": {
                "paid_total": paid_total,
                "refund_total": refund_total,
                "penalty_total": penalty_total,
            },
            "formula": "alloc_net == paid_total - refund_total - credited_total",
        }

    def check_invoice(
        self,
        invoice: Invoice,
        *,
        request_ctx: RequestContext | None = None,
        audit: bool = True,
    ) -> None:
        violations = rules.validate_invoice(invoice)
        if violations:
            violation = self._build_error(
                entity_type="invoice",
                entity_id=invoice.id,
                violations=violations,
                context=self._invoice_snapshot(invoice),
            )
            if audit:
                self.audit_violation(violation, request_ctx=request_ctx, extra_payload={"invoice_id": invoice.id})
            raise violation

    def check_payment_application(
        self,
        invoice: Invoice,
        *,
        amount: int,
        idempotency_key: str,
        request_ctx: RequestContext | None = None,
        audit: bool = True,
    ) -> None:
        violations = rules.validate_payment_application(invoice, amount=amount)
        if violations:
            violation = self._build_error(
                entity_type="payment",
                entity_id=idempotency_key,
                violations=violations,
                context={
                    "payment_reference": idempotency_key,
                    **self._invoice_snapshot(invoice),
                },
            )
            if audit:
                self.audit_violation(violation, request_ctx=request_ctx, extra_payload={"invoice_id": invoice.id})
            raise violation

    def check_refund(
        self,
        invoice: Invoice,
        *,
        amount: int,
        reference: str,
        request_ctx: RequestContext | None = None,
        audit: bool = True,
    ) -> None:
        violations = rules.validate_refund(invoice, amount=amount)
        if violations:
            violation = self._build_error(
                entity_type="payment",
                entity_id=reference,
                violations=violations,
                context={
                    "refund_reference": reference,
                    **self._invoice_snapshot(invoice),
                },
            )
            if audit:
                self.audit_violation(
                    violation,
                    request_ctx=request_ctx,
                    extra_payload={"invoice_id": invoice.id, "refund_reference": reference},
                )
            raise violation

    def check_settlement_allocation(
        self,
        *,
        invoice: Invoice,
        amount: int,
        settlement_period_id: str,
        source_type: SettlementSourceType,
        source_id: str,
        override: bool,
        request_ctx: RequestContext | None = None,
        audit: bool = True,
    ) -> None:
        period = (
            self.db.query(BillingPeriod)
            .filter(BillingPeriod.id == settlement_period_id)
            .one_or_none()
        )
        if not period:
            violation = self._build_error(
                entity_type="invoice",
                entity_id=invoice.id,
                violations=[
                    rules.InvariantViolation(
                        name="settlement.period_missing",
                        expected="period_exists",
                        actual=settlement_period_id,
                    )
                ],
            )
            if audit:
                self.audit_violation(violation, request_ctx=request_ctx)
            raise violation
        period_violations = rules.validate_settlement_period(status=period.status, override=override)
        if period_violations:
            violation = self._build_error(
                entity_type="invoice",
                entity_id=invoice.id,
                violations=period_violations,
            )
            if audit:
                self.audit_violation(
                    violation,
                    request_ctx=request_ctx,
                    extra_payload={"settlement_period_id": settlement_period_id},
                )
            raise violation

        totals = (
            self.db.query(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                InvoiceSettlementAllocation.source_type == SettlementSourceType.PAYMENT,
                                InvoiceSettlementAllocation.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_payments"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                InvoiceSettlementAllocation.source_type == SettlementSourceType.CREDIT_NOTE,
                                InvoiceSettlementAllocation.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_credits"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                InvoiceSettlementAllocation.source_type == SettlementSourceType.REFUND,
                                InvoiceSettlementAllocation.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_refunds"),
                func.count(InvoiceSettlementAllocation.id).label("allocation_count"),
            )
            .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
            .one()
        )
        total_payments = int(totals.total_payments or 0)
        total_credits = int(totals.total_credits or 0)
        total_refunds = int(totals.total_refunds or 0)
        allocation_count = int(totals.allocation_count or 0)

        if source_type == SettlementSourceType.PAYMENT:
            total_payments += int(amount)
        elif source_type == SettlementSourceType.CREDIT_NOTE:
            total_credits += int(amount)
        elif source_type == SettlementSourceType.REFUND:
            total_refunds += int(amount)

        total_allocated = total_payments - total_credits - total_refunds
        net_coverage = (
            int(invoice.amount_paid or 0)
            - int(getattr(invoice, "amount_refunded", 0) or 0)
            - int(getattr(invoice, "credited_amount", 0) or 0)
        )
        invoice_total = int(invoice.total_with_tax or invoice.total_amount or 0)
        total_violations = rules.validate_settlement_total(
            total_allocated=total_allocated,
            net_coverage=net_coverage,
            invoice_total=invoice_total,
        )
        if total_violations:
            allocations = (
                self.db.query(InvoiceSettlementAllocation)
                .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
                .all()
            )
            context = {
                **self._invoice_snapshot(invoice),
                "settlement_period_id": settlement_period_id,
                "source_type": source_type.value,
                "source_id": source_id,
                "allocation_totals": {
                    "total_payments": total_payments,
                    "total_credits": total_credits,
                    "total_refunds": total_refunds,
                    "allocation_count": allocation_count,
                    "net_allocated": total_allocated,
                    "net_coverage": net_coverage,
                },
            }
            if self._is_test_mode():
                context["debug"] = self._settlement_debug_snapshot(
                    invoice=invoice,
                    allocations=allocations,
                    total_payments=total_payments,
                    total_credits=total_credits,
                    total_refunds=total_refunds,
                )
            violation = self._build_error(
                entity_type="invoice",
                entity_id=invoice.id,
                violations=total_violations,
                context=context,
            )
            if audit:
                self.audit_violation(
                    violation,
                    request_ctx=request_ctx,
                    extra_payload={
                        "settlement_period_id": settlement_period_id,
                        "invoice_total": invoice_total,
                    },
                )
            raise violation

    def check_ledger_lines(
        self,
        *,
        lines: Iterable[dict],
        posting_id: UUID,
        request_ctx: RequestContext | None = None,
    ) -> None:
        violations = rules.validate_ledger_lines(lines)
        if violations:
            violation = self._build_error(
                entity_type="ledger_transaction",
                entity_id=str(posting_id),
                violations=violations,
                ledger_transaction_id=str(posting_id),
            )
            self.audit_violation(violation, request_ctx=request_ctx)
            raise violation

        account_ids = {int(line["account_id"]) for line in lines}
        if not account_ids:
            return
        accounts = (
            self.db.query(Account)
            .filter(Account.id.in_(account_ids))
            .all()
        )
        currency_by_id = {account.id: account.currency for account in accounts}
        currency_violations: list[rules.InvariantViolation] = []
        for line in lines:
            account_id = int(line["account_id"])
            expected_currency = currency_by_id.get(account_id)
            if expected_currency is None:
                currency_violations.append(
                    rules.InvariantViolation(
                        name="ledger.account_missing",
                        expected="account_exists",
                        actual=account_id,
                    )
                )
                continue
            line_currency = str(line["currency"])
            if line_currency != expected_currency:
                currency_violations.append(
                    rules.InvariantViolation(
                        name="ledger.currency_match",
                        expected=expected_currency,
                        actual={"account_id": account_id, "currency": line_currency},
                    )
                )

        if currency_violations:
            violation = self._build_error(
                entity_type="ledger_transaction",
                entity_id=str(posting_id),
                violations=currency_violations,
                ledger_transaction_id=str(posting_id),
            )
            self.audit_violation(violation, request_ctx=request_ctx)
            raise violation

    @staticmethod
    def serialize_ledger_lines(lines: Iterable) -> list[dict[str, object]]:
        serialized: list[dict[str, object]] = []
        for line in lines:
            serialized.append(
                {
                    "account_id": line.account_id,
                    "direction": line.direction,
                    "amount": Decimal(str(line.amount)),
                    "currency": line.currency,
                }
            )
        return serialized


__all__ = ["FinancialInvariantChecker"]
