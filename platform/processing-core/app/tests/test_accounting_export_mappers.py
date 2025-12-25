from datetime import datetime, timezone
from uuid import uuid4

from app.models.accounting_export_batch import (
    AccountingExportBatch,
    AccountingExportFormat,
    AccountingExportState,
    AccountingExportType,
)
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice, InvoiceStatus
from app.services.accounting_export.canonical import build_entry_id
from app.services.accounting_export.mappers import map_charges_entries, map_settlement_entries


def _make_period(*, status: BillingPeriodStatus) -> BillingPeriod:
    period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)
    return BillingPeriod(
        id=str(uuid4()),
        period_type=BillingPeriodType.ADHOC,
        start_at=period_start,
        end_at=period_end,
        tz="UTC",
        status=status,
        finalized_at=period_start if status != BillingPeriodStatus.OPEN else None,
        locked_at=period_start if status == BillingPeriodStatus.LOCKED else None,
    )


def _make_batch(export_type: AccountingExportType) -> AccountingExportBatch:
    return AccountingExportBatch(
        id=str(uuid4()),
        tenant_id=1,
        billing_period_id=str(uuid4()),
        export_type=export_type,
        format=AccountingExportFormat.CSV,
        state=AccountingExportState.CREATED,
        idempotency_key="test",
    )


def test_map_charges_entries_from_invoice():
    period = _make_period(status=BillingPeriodStatus.FINALIZED)
    invoice = Invoice(
        id=str(uuid4()),
        client_id="client-1",
        number="INV-100",
        period_from=period.start_at.date(),
        period_to=period.end_at.date(),
        currency="RUB",
        billing_period_id=period.id,
        total_amount=1000,
        tax_amount=200,
        total_with_tax=1200,
        amount_paid=0,
        amount_due=1200,
        status=InvoiceStatus.ISSUED,
        issued_at=period.start_at,
    )
    batch = _make_batch(AccountingExportType.CHARGES)

    entries = map_charges_entries(batch=batch, invoices=[invoice])
    assert len(entries) == 1
    entry = entries[0]
    assert entry.document_type == "INVOICE"
    assert entry.document_id == invoice.id
    assert entry.amount_gross == 1200
    assert entry.amount_net == 1000
    assert entry.vat_amount == 200
    assert entry.posting_date == period.start_at.date()
    assert entry.entry_id == build_entry_id(entry)


def test_map_settlement_entries_from_allocation():
    charge_period = _make_period(status=BillingPeriodStatus.FINALIZED)
    settlement_period = _make_period(status=BillingPeriodStatus.FINALIZED)
    invoice = Invoice(
        id=str(uuid4()),
        client_id="client-2",
        number="INV-SET-2",
        period_from=charge_period.start_at.date(),
        period_to=charge_period.end_at.date(),
        currency="RUB",
        billing_period_id=charge_period.id,
        total_amount=1500,
        tax_amount=300,
        total_with_tax=1800,
        amount_paid=1500,
        amount_due=0,
        status=InvoiceStatus.PAID,
        issued_at=charge_period.start_at,
    )
    payment = InvoicePayment(
        id=str(uuid4()),
        invoice_id=invoice.id,
        amount=1500,
        currency="RUB",
        provider="bank",
        external_ref="payment-2",
        idempotency_key="payment-2",
    )
    allocation = InvoiceSettlementAllocation(
        id=str(uuid4()),
        invoice_id=invoice.id,
        tenant_id=1,
        client_id=invoice.client_id,
        settlement_period_id=settlement_period.id,
        source_type=SettlementSourceType.PAYMENT,
        source_id=payment.id,
        amount=1500,
        currency="RUB",
        applied_at=settlement_period.start_at,
    )
    batch = _make_batch(AccountingExportType.SETTLEMENT)

    entries = map_settlement_entries(
        batch=batch,
        allocations=[allocation],
        invoices={invoice.id: invoice},
        billing_periods={str(charge_period.id): charge_period},
        payments={payment.id: payment},
        credits={},
    )
    entry = entries[0]
    assert entry.document_type == "PAYMENT"
    assert entry.source_type == "PAYMENT"
    assert entry.source_id == payment.id
    assert entry.period_from == charge_period.start_at.date()
    assert entry.period_to == charge_period.end_at.date()
    assert entry.provider == "bank"
    assert entry.external_ref == "payment-2"
