import hashlib
from datetime import date, datetime, timezone

from app.services.accounting_export.canonical import AccountingEntry, build_entry_id
from app.services.accounting_export.formats.csv_1c import serialize_charges_csv
from app.services.accounting_export.formats.json_sap import serialize_sap_json


def _make_entry(*, entry_id: str, document_id: str, amount: int) -> AccountingEntry:
    return AccountingEntry(
        entry_id=entry_id,
        batch_id="batch-1",
        export_type="CHARGES",
        tenant_id=1,
        client_id="client-1",
        currency="RUB",
        posting_date=date(2024, 1, 31),
        period_from=date(2024, 1, 1),
        period_to=date(2024, 1, 31),
        document_type="INVOICE",
        document_id=document_id,
        document_number="INV-1",
        amount_gross=amount,
        vat_rate=None,
        vat_amount=200,
        amount_net=1000,
        counterparty_ref=None,
        contract_ref=None,
        cost_center=None,
        source_type=None,
        source_id=None,
        external_ref=None,
        provider=None,
        meta={},
    )


def test_deterministic_csv_serializer_orders_entries():
    entry_one = _make_entry(entry_id="", document_id="doc-1", amount=1200)
    entry_one = AccountingEntry(**{**entry_one.__dict__, "entry_id": build_entry_id(entry_one)})
    entry_two = _make_entry(entry_id="", document_id="doc-2", amount=1300)
    entry_two = AccountingEntry(**{**entry_two.__dict__, "entry_id": build_entry_id(entry_two)})

    payload_a = serialize_charges_csv([entry_two, entry_one])
    payload_b = serialize_charges_csv([entry_one, entry_two])

    assert payload_a == payload_b
    assert hashlib.sha256(payload_a).hexdigest() == hashlib.sha256(payload_b).hexdigest()


def test_deterministic_json_serializer_is_stable():
    entry = _make_entry(entry_id="", document_id="doc-1", amount=1200)
    entry = AccountingEntry(**{**entry.__dict__, "entry_id": build_entry_id(entry)})

    generated_at = datetime(2024, 1, 31, tzinfo=timezone.utc)
    payload_a, checksum_a = serialize_sap_json(
        batch_id="batch-1",
        export_type="CHARGES",
        generated_at=generated_at,
        entries=[entry],
        records_count=1,
    )
    payload_b, checksum_b = serialize_sap_json(
        batch_id="batch-1",
        export_type="CHARGES",
        generated_at=generated_at,
        entries=[entry],
        records_count=1,
    )

    assert payload_a == payload_b
    assert checksum_a == checksum_b
