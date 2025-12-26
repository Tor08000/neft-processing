from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.audit_log import AuditVisibility
from app.models.billing_period import BillingPeriod
from app.models.finance import InvoiceSettlementAllocation
from app.models.invoice import Invoice
from app.services.audit_service import AuditService, RequestContext
from app.services.finance_invariants.errors import FinancialInvariantViolation
from app.services.finance_invariants import rules


class FinancialInvariantChecker:
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    def _audit_and_raise(
        self,
        *,
        entity_type: str,
        entity_id: str,
        violations: list[rules.InvariantViolation],
        request_ctx: RequestContext | None = None,
        ledger_transaction_id: str | None = None,
        extra_payload: dict | None = None,
    ) -> None:
        payload = {
            "entity": entity_type,
            "invariants": [asdict(violation) for violation in violations],
            "ledger_transaction_id": ledger_transaction_id,
        }
        if extra_payload:
            payload.update(extra_payload)

        self.audit_service.audit(
            event_type="FINANCIAL_INVARIANT_VIOLATION",
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="VALIDATE",
            visibility=AuditVisibility.INTERNAL,
            after=payload,
            request_ctx=request_ctx,
            reason=violations[0].name if violations else None,
        )

        primary = violations[0]
        raise FinancialInvariantViolation(
            entity_type=entity_type,
            entity_id=str(entity_id),
            invariant_name=primary.name,
            expected=primary.expected,
            actual=primary.actual,
            ledger_transaction_id=ledger_transaction_id,
        )

    def check_invoice(self, invoice: Invoice, *, request_ctx: RequestContext | None = None) -> None:
        violations = rules.validate_invoice(invoice)
        if violations:
            self._audit_and_raise(
                entity_type="invoice",
                entity_id=invoice.id,
                violations=violations,
                request_ctx=request_ctx,
                extra_payload={"invoice_id": invoice.id},
            )

    def check_payment_application(
        self,
        invoice: Invoice,
        *,
        amount: int,
        idempotency_key: str,
        request_ctx: RequestContext | None = None,
    ) -> None:
        violations = rules.validate_payment_application(invoice, amount=amount)
        if violations:
            self._audit_and_raise(
                entity_type="payment",
                entity_id=idempotency_key,
                violations=violations,
                request_ctx=request_ctx,
                extra_payload={"invoice_id": invoice.id},
            )

    def check_refund(
        self,
        invoice: Invoice,
        *,
        amount: int,
        reference: str,
        request_ctx: RequestContext | None = None,
    ) -> None:
        violations = rules.validate_refund(invoice, amount=amount)
        if violations:
            self._audit_and_raise(
                entity_type="payment",
                entity_id=reference,
                violations=violations,
                request_ctx=request_ctx,
                extra_payload={"invoice_id": invoice.id, "refund_reference": reference},
            )

    def check_settlement_allocation(
        self,
        *,
        invoice: Invoice,
        amount: int,
        settlement_period_id: str,
        override: bool,
        request_ctx: RequestContext | None = None,
    ) -> None:
        period = (
            self.db.query(BillingPeriod)
            .filter(BillingPeriod.id == settlement_period_id)
            .one_or_none()
        )
        if not period:
            self._audit_and_raise(
                entity_type="invoice",
                entity_id=invoice.id,
                violations=[
                    rules.InvariantViolation(
                        name="settlement.period_missing",
                        expected="period_exists",
                        actual=settlement_period_id,
                    )
                ],
                request_ctx=request_ctx,
            )
        period_violations = rules.validate_settlement_period(status=period.status, override=override)
        if period_violations:
            self._audit_and_raise(
                entity_type="invoice",
                entity_id=invoice.id,
                violations=period_violations,
                request_ctx=request_ctx,
                extra_payload={"settlement_period_id": settlement_period_id},
            )

        total_allocated = (
            self.db.query(func.coalesce(func.sum(InvoiceSettlementAllocation.amount), 0))
            .filter(InvoiceSettlementAllocation.invoice_id == invoice.id)
            .scalar()
        )
        total_allocated = int(total_allocated or 0) + int(amount)
        invoice_total = int(invoice.total_with_tax or invoice.total_amount or 0)
        total_violations = rules.validate_settlement_total(
            total_allocated=total_allocated,
            invoice_total=invoice_total,
        )
        if total_violations:
            self._audit_and_raise(
                entity_type="invoice",
                entity_id=invoice.id,
                violations=total_violations,
                request_ctx=request_ctx,
                extra_payload={
                    "settlement_period_id": settlement_period_id,
                    "invoice_total": invoice_total,
                },
            )

    def check_ledger_lines(
        self,
        *,
        lines: Iterable[dict],
        posting_id: UUID,
        request_ctx: RequestContext | None = None,
    ) -> None:
        violations = rules.validate_ledger_lines(lines)
        if violations:
            self._audit_and_raise(
                entity_type="ledger_transaction",
                entity_id=str(posting_id),
                violations=violations,
                request_ctx=request_ctx,
                ledger_transaction_id=str(posting_id),
            )

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
            self._audit_and_raise(
                entity_type="ledger_transaction",
                entity_id=str(posting_id),
                violations=currency_violations,
                request_ctx=request_ctx,
                ledger_transaction_id=str(posting_id),
            )

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
