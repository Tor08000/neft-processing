from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.billing_reconciliation import (
    BillingReconciliationItem,
    BillingReconciliationRun,
    BillingReconciliationStatus,
    BillingReconciliationVerdict,
)
from app.models.invoice import Invoice, InvoiceLine
from app.models.ledger_entry import LedgerEntry, LedgerDirection
from app.models.operation import Operation, OperationStatus


class BillingReconciliationService:
    def __init__(self, db: Session):
        self.db = db

    def _load_period(self, billing_period_id: str) -> BillingPeriod:
        period = self.db.query(BillingPeriod).filter(BillingPeriod.id == billing_period_id).one_or_none()
        if period is None:
            raise ValueError("Billing period not found")
        if period.status not in (BillingPeriodStatus.LOCKED, BillingPeriodStatus.FINALIZED):
            raise ValueError("Reconciliation allowed only for locked or finalized periods")
        return period

    def _summarize_ledger(self, operation_pk: str) -> tuple[Decimal, Decimal]:
        debit = (
            self.db.query(LedgerEntry)
            .with_entities(LedgerEntry.amount)
            .filter(LedgerEntry.operation_id == operation_pk)
            .filter(LedgerEntry.direction == LedgerDirection.DEBIT)
        )
        credit = (
            self.db.query(LedgerEntry)
            .with_entities(LedgerEntry.amount)
            .filter(LedgerEntry.operation_id == operation_pk)
            .filter(LedgerEntry.direction == LedgerDirection.CREDIT)
        )
        debit_sum = sum((row.amount for row in debit), start=Decimal("0"))
        credit_sum = sum((row.amount for row in credit), start=Decimal("0"))
        return debit_sum, credit_sum

    def run(self, billing_period_id: str) -> BillingReconciliationRun:
        period = self._load_period(billing_period_id)

        run = BillingReconciliationRun(
            billing_period_id=period.id,
            status=BillingReconciliationStatus.OK,
        )
        self.db.add(run)
        self.db.flush()

        invoices = (
            self.db.query(Invoice)
            .filter(Invoice.billing_period_id == period.id)
            .order_by(Invoice.created_at.asc())
            .all()
        )
        total_invoices = 0
        ok_count = mismatch_count = missing_ledger_count = 0

        for invoice in invoices:
            total_invoices += 1
            verdict = BillingReconciliationVerdict.OK
            diff: dict[str, object] = {}

            lines: list[InvoiceLine] = list(invoice.lines or [])
            line_sum = sum(int(line.line_amount or 0) for line in lines)
            if line_sum != int(invoice.total_amount or 0):
                verdict = BillingReconciliationVerdict.MISMATCH
                diff["invoice_total_mismatch"] = {"expected": int(invoice.total_amount or 0), "actual": line_sum}

            missing_ops: list[str] = []
            bad_status_ops: list[str] = []
            missing_ledger_ops: list[str] = []
            ledger_diffs: dict[str, dict[str, str]] = {}

            for line in lines:
                operation = (
                    self.db.query(Operation).filter(Operation.operation_id == line.operation_id).one_or_none()
                )
                if operation is None:
                    missing_ops.append(line.operation_id)
                    verdict = BillingReconciliationVerdict.MISMATCH
                    continue
                if operation.status not in (OperationStatus.CAPTURED, OperationStatus.COMPLETED):
                    bad_status_ops.append(operation.operation_id)
                    verdict = BillingReconciliationVerdict.MISMATCH

                debit_sum, credit_sum = self._summarize_ledger(str(operation.id))
                if debit_sum == 0 and credit_sum == 0:
                    missing_ledger_ops.append(operation.operation_id)
                    verdict = BillingReconciliationVerdict.MISSING_LEDGER
                else:
                    ledger_diffs[operation.operation_id] = {
                        "debit": str(debit_sum),
                        "credit": str(credit_sum),
                        "line_amount": str(line.line_amount),
                    }

            if missing_ops:
                diff["missing_operations"] = missing_ops
            if bad_status_ops:
                diff["invalid_operation_status"] = bad_status_ops
            if missing_ledger_ops:
                diff["missing_ledger"] = missing_ledger_ops
            if ledger_diffs:
                diff["ledger_summary"] = ledger_diffs

            item = BillingReconciliationItem(
                run_id=run.id,
                invoice_id=invoice.id,
                client_id=invoice.client_id,
                currency=invoice.currency,
                verdict=verdict,
                diff_json=diff or None,
            )
            self.db.add(item)

            if verdict == BillingReconciliationVerdict.OK:
                ok_count += 1
            elif verdict == BillingReconciliationVerdict.MISSING_LEDGER:
                missing_ledger_count += 1
            else:
                mismatch_count += 1

        run.total_invoices = total_invoices
        run.ok_count = ok_count
        run.mismatch_count = mismatch_count
        run.missing_ledger_count = missing_ledger_count
        run.status = (
            BillingReconciliationStatus.OK
            if mismatch_count == 0 and missing_ledger_count == 0
            else BillingReconciliationStatus.PARTIAL
        )
        run.finished_at = run.finished_at or datetime.now(timezone.utc)
        self.db.flush()
        return run
