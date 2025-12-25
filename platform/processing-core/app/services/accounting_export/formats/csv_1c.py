from __future__ import annotations

from app.services.accounting_export.canonical import AccountingEntry
from app.services.accounting_export.serializer import serialize_entries_csv

CSV_PREAMBLE = "# minor_units=2"

CHARGES_COLUMNS = [
    "batch_id",
    "entry_id",
    "tenant_id",
    "client_id",
    "posting_date",
    "period_from",
    "period_to",
    "document_type",
    "document_id",
    "document_number",
    "currency",
    "amount_gross",
    "vat_amount",
    "amount_net",
    "contract_ref",
    "counterparty_ref",
]

SETTLEMENT_COLUMNS = [
    "batch_id",
    "entry_id",
    "tenant_id",
    "client_id",
    "posting_date",
    "document_id",
    "document_number",
    "source_type",
    "source_id",
    "provider",
    "external_ref",
    "currency",
    "amount_gross",
    "charge_period_from",
    "charge_period_to",
    "contract_ref",
    "counterparty_ref",
]


def _charges_row(entry: AccountingEntry) -> dict[str, object | None]:
    return {
        "batch_id": entry.batch_id,
        "entry_id": entry.entry_id,
        "tenant_id": entry.tenant_id,
        "client_id": entry.client_id,
        "posting_date": entry.posting_date,
        "period_from": entry.period_from,
        "period_to": entry.period_to,
        "document_type": entry.document_type,
        "document_id": entry.document_id,
        "document_number": entry.document_number,
        "currency": entry.currency,
        "amount_gross": entry.amount_gross,
        "vat_amount": entry.vat_amount,
        "amount_net": entry.amount_net,
        "contract_ref": entry.contract_ref,
        "counterparty_ref": entry.counterparty_ref,
    }


def _settlement_row(entry: AccountingEntry) -> dict[str, object | None]:
    return {
        "batch_id": entry.batch_id,
        "entry_id": entry.entry_id,
        "tenant_id": entry.tenant_id,
        "client_id": entry.client_id,
        "posting_date": entry.posting_date,
        "document_id": entry.document_id,
        "document_number": entry.document_number,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "provider": entry.provider,
        "external_ref": entry.external_ref,
        "currency": entry.currency,
        "amount_gross": entry.amount_gross,
        "charge_period_from": entry.period_from,
        "charge_period_to": entry.period_to,
        "contract_ref": entry.contract_ref,
        "counterparty_ref": entry.counterparty_ref,
    }


def serialize_charges_csv(entries: list[AccountingEntry], *, delimiter: str = ";") -> bytes:
    return serialize_entries_csv(
        entries,
        columns=CHARGES_COLUMNS,
        delimiter=delimiter,
        preamble=CSV_PREAMBLE,
        row_builder=_charges_row,
    )


def serialize_settlement_csv(entries: list[AccountingEntry], *, delimiter: str = ";") -> bytes:
    return serialize_entries_csv(
        entries,
        columns=SETTLEMENT_COLUMNS,
        delimiter=delimiter,
        preamble=CSV_PREAMBLE,
        row_builder=_settlement_row,
    )


__all__ = [
    "CHARGES_COLUMNS",
    "CSV_PREAMBLE",
    "SETTLEMENT_COLUMNS",
    "serialize_charges_csv",
    "serialize_settlement_csv",
]
