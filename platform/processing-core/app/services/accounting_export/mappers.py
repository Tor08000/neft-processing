from __future__ import annotations

from dataclasses import replace
from app.models.accounting_export_batch import AccountingExportBatch
from app.models.billing_period import BillingPeriod
from app.models.finance import CreditNote, InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice
from app.services.accounting_export.canonical import AccountingEntry, build_entry_id


def _document_number(invoice: Invoice) -> str | None:
    return invoice.external_number or invoice.number


def _posting_date_for_invoice(invoice: Invoice) -> date:
    if invoice.issued_at:
        return invoice.issued_at.date()
    return invoice.period_to


def _entry_with_id(entry: AccountingEntry) -> AccountingEntry:
    entry_id = build_entry_id(entry)
    return replace(entry, entry_id=entry_id)


def map_charges_entries(
    *,
    batch: AccountingExportBatch,
    invoices: list[Invoice],
) -> list[AccountingEntry]:
    entries: list[AccountingEntry] = []
    for invoice in invoices:
        entry = AccountingEntry(
            entry_id="",
            batch_id=str(batch.id),
            export_type=batch.export_type.value,
            tenant_id=batch.tenant_id,
            client_id=invoice.client_id,
            currency=invoice.currency,
            posting_date=_posting_date_for_invoice(invoice),
            period_from=invoice.period_from,
            period_to=invoice.period_to,
            document_type="INVOICE",
            document_id=str(invoice.id),
            document_number=_document_number(invoice),
            amount_gross=int(invoice.total_with_tax),
            vat_rate=None,
            vat_amount=int(invoice.tax_amount) if invoice.tax_amount is not None else None,
            amount_net=int(invoice.total_amount) if invoice.total_amount is not None else None,
            counterparty_ref=None,
            contract_ref=None,
            cost_center=None,
            source_type=None,
            source_id=None,
            external_ref=None,
            provider=None,
            meta={},
        )
        entries.append(_entry_with_id(entry))
    return entries


def map_settlement_entries(
    *,
    batch: AccountingExportBatch,
    allocations: list[InvoiceSettlementAllocation],
    invoices: dict[str, Invoice],
    billing_periods: dict[str, BillingPeriod],
    payments: dict[str, InvoicePayment],
    credits: dict[str, CreditNote],
) -> list[AccountingEntry]:
    entries: list[AccountingEntry] = []
    for allocation in allocations:
        invoice = invoices.get(allocation.invoice_id)
        charge_period = billing_periods.get(str(invoice.billing_period_id)) if invoice else None
        charge_period_from = charge_period.start_at.date() if charge_period else None
        charge_period_to = charge_period.end_at.date() if charge_period else None

        provider = None
        external_ref = None
        if allocation.source_type == SettlementSourceType.PAYMENT:
            payment = payments.get(allocation.source_id)
            if payment:
                provider = payment.provider
                external_ref = payment.external_ref
        else:
            credit = credits.get(allocation.source_id)
            if credit:
                provider = credit.provider
                external_ref = credit.external_ref

        document_number = _document_number(invoice) if invoice else None

        entry = AccountingEntry(
            entry_id="",
            batch_id=str(batch.id),
            export_type=batch.export_type.value,
            tenant_id=batch.tenant_id,
            client_id=allocation.client_id,
            currency=allocation.currency,
            posting_date=allocation.applied_at.date(),
            period_from=charge_period_from,
            period_to=charge_period_to,
            document_type=allocation.source_type.value,
            document_id=str(allocation.invoice_id),
            document_number=document_number,
            amount_gross=int(allocation.amount),
            vat_rate=None,
            vat_amount=None,
            amount_net=None,
            counterparty_ref=None,
            contract_ref=None,
            cost_center=None,
            source_type=allocation.source_type.value,
            source_id=str(allocation.source_id),
            external_ref=external_ref,
            provider=provider,
            meta=allocation.meta or {},
        )
        entries.append(_entry_with_id(entry))
    return entries


__all__ = ["map_charges_entries", "map_settlement_entries"]
