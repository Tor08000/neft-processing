from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.accounting_export_batch import AccountingExportBatch
from app.models.erp_exports import ErpReconciliationRun, ErpReconciliationStatus, ErpSystemType
from app.services.accounting_export_service import AccountingExportService
from app.services.audit_service import AuditService, RequestContext


@dataclass(frozen=True)
class ErpReconciliationReport:
    checksum_sha256: str
    records_count: int
    totals: dict[str, int]


class ErpReconciliationService:
    def __init__(self, db: Session):
        self.db = db

    def reconcile_report(
        self,
        *,
        batch_id: str,
        system_type: ErpSystemType,
        report: ErpReconciliationReport,
        request_ctx: RequestContext | None,
    ) -> ErpReconciliationRun:
        batch = AccountingExportService(self.db)._load_batch(batch_id)
        expected = self._expected_metrics(batch)
        status, diff = self._compare_report(expected, report)
        now = datetime.now(timezone.utc)
        run = ErpReconciliationRun(
            tenant_id=batch.tenant_id,
            client_id=None,
            export_batch_id=str(batch.id),
            system_type=system_type,
            status=status,
            started_at=now,
            finished_at=now,
            metrics={
                "expected": expected,
                "reported": {
                    "checksum_sha256": report.checksum_sha256,
                    "records_count": report.records_count,
                    "totals": report.totals,
                },
                "diff": diff,
            },
        )
        self.db.add(run)
        self.db.flush()
        AuditService(self.db).audit(
            event_type="ERP_RECONCILIATION_RECORDED",
            entity_type="erp_reconciliation_run",
            entity_id=str(run.id),
            action="RECONCILE",
            after={
                "batch_id": str(batch.id),
                "system_type": system_type.value,
                "status": status.value,
                "diff": diff,
            },
            request_ctx=request_ctx,
        )
        return run

    def _expected_metrics(self, batch: AccountingExportBatch) -> dict[str, Any]:
        export_service = AccountingExportService(self.db)
        if batch.export_type.value == "CHARGES":
            entries = export_service._load_charge_entries(batch)
        else:
            entries = export_service._load_settlement_entries(batch)
        totals = {
            "amount_gross": sum(entry.amount_gross for entry in entries),
            "vat_amount": sum(entry.vat_amount or 0 for entry in entries),
            "amount_net": sum(entry.amount_net or 0 for entry in entries),
        }
        return {
            "checksum_sha256": batch.checksum_sha256,
            "records_count": batch.records_count,
            "totals": totals,
        }

    @staticmethod
    def _compare_report(
        expected: dict[str, Any], report: ErpReconciliationReport
    ) -> tuple[ErpReconciliationStatus, dict[str, Any]]:
        diff: dict[str, Any] = {}
        if expected.get("checksum_sha256") != report.checksum_sha256:
            diff["checksum_sha256"] = {
                "expected": expected.get("checksum_sha256"),
                "reported": report.checksum_sha256,
            }
        if expected.get("records_count") != report.records_count:
            diff["records_count"] = {
                "expected": expected.get("records_count"),
                "reported": report.records_count,
            }
        expected_totals = expected.get("totals") or {}
        totals_diff = {
            key: {"expected": expected_totals.get(key), "reported": report.totals.get(key)}
            for key in set(expected_totals) | set(report.totals)
            if expected_totals.get(key) != report.totals.get(key)
        }
        if totals_diff:
            diff["totals"] = totals_diff
        status = ErpReconciliationStatus.OK if not diff else ErpReconciliationStatus.MISMATCH
        return status, diff


__all__ = ["ErpReconciliationReport", "ErpReconciliationService"]
