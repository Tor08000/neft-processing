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

ERP_MAPPING_COLUMNS = [
    "gl_account",
    "subaccount_1",
    "subaccount_2",
    "subaccount_3",
    "cost_item",
    "vat_code",
    "counterparty_ref_mode",
    "nomenclature_ref",
]

CHARGES_COLUMNS_ERP = CHARGES_COLUMNS + ERP_MAPPING_COLUMNS

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

SETTLEMENT_COLUMNS_ERP = SETTLEMENT_COLUMNS + ERP_MAPPING_COLUMNS


def _mapping_row(entry: AccountingEntry) -> dict[str, object | None]:
    mapping = entry.meta.get("erp_mapping") or {}
    return {
        "gl_account": mapping.get("gl_account"),
        "subaccount_1": mapping.get("subaccount_1"),
        "subaccount_2": mapping.get("subaccount_2"),
        "subaccount_3": mapping.get("subaccount_3"),
        "cost_item": mapping.get("cost_item"),
        "vat_code": mapping.get("vat_code"),
        "counterparty_ref_mode": mapping.get("counterparty_ref_mode"),
        "nomenclature_ref": mapping.get("nomenclature_ref"),
    }


def _charges_row(entry: AccountingEntry, *, include_mapping: bool) -> dict[str, object | None]:
    row = {
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
    if include_mapping:
        row.update(_mapping_row(entry))
    return row


def _settlement_row(entry: AccountingEntry, *, include_mapping: bool) -> dict[str, object | None]:
    row = {
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
    if include_mapping:
        row.update(_mapping_row(entry))
    return row


def serialize_charges_csv(
    entries: list[AccountingEntry],
    *,
    delimiter: str = ";",
    include_mapping: bool = False,
) -> bytes:
    return serialize_entries_csv(
        entries,
        columns=CHARGES_COLUMNS_ERP if include_mapping else CHARGES_COLUMNS,
        delimiter=delimiter,
        preamble=CSV_PREAMBLE,
        row_builder=lambda entry: _charges_row(entry, include_mapping=include_mapping),
    )


def serialize_settlement_csv(
    entries: list[AccountingEntry],
    *,
    delimiter: str = ";",
    include_mapping: bool = False,
) -> bytes:
    return serialize_entries_csv(
        entries,
        columns=SETTLEMENT_COLUMNS_ERP if include_mapping else SETTLEMENT_COLUMNS,
        delimiter=delimiter,
        preamble=CSV_PREAMBLE,
        row_builder=lambda entry: _settlement_row(entry, include_mapping=include_mapping),
    )


__all__ = [
    "CHARGES_COLUMNS",
    "CHARGES_COLUMNS_ERP",
    "CSV_PREAMBLE",
    "ERP_MAPPING_COLUMNS",
    "SETTLEMENT_COLUMNS",
    "SETTLEMENT_COLUMNS_ERP",
    "serialize_charges_csv",
    "serialize_settlement_csv",
]
