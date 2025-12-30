from app.models.erp_exports import ErpReconciliationStatus
from app.services.accounting_export.erp_reconciliation_service import (
    ErpReconciliationReport,
    ErpReconciliationService,
)


def test_reconciliation_compare_ok():
    expected = {
        "checksum_sha256": "abc",
        "records_count": 2,
        "totals": {"amount_gross": 300, "vat_amount": 50, "amount_net": 250},
    }
    report = ErpReconciliationReport(
        checksum_sha256="abc",
        records_count=2,
        totals={"amount_gross": 300, "vat_amount": 50, "amount_net": 250},
    )
    status, diff = ErpReconciliationService._compare_report(expected, report)
    assert status == ErpReconciliationStatus.OK
    assert diff == {}


def test_reconciliation_compare_mismatch():
    expected = {
        "checksum_sha256": "abc",
        "records_count": 2,
        "totals": {"amount_gross": 300, "vat_amount": 50, "amount_net": 250},
    }
    report = ErpReconciliationReport(
        checksum_sha256="def",
        records_count=3,
        totals={"amount_gross": 310, "vat_amount": 50, "amount_net": 260},
    )
    status, diff = ErpReconciliationService._compare_report(expected, report)
    assert status == ErpReconciliationStatus.MISMATCH
    assert "checksum_sha256" in diff
    assert "records_count" in diff
    assert "totals" in diff
