from datetime import date

from app.models.erp_exports import ErpCounterpartyRefMode, ErpMappingMatchKind, ErpMappingRule
from app.services.accounting_export.canonical import AccountingEntry, build_entry_id
from app.services.accounting_export.erp_mapping_service import ErpMappingService


def _entry(meta: dict | None = None) -> AccountingEntry:
    return AccountingEntry(
        entry_id="",
        batch_id="batch-1",
        export_type="CHARGES",
        tenant_id=1,
        client_id="client-1",
        currency="RUB",
        posting_date=date(2024, 1, 1),
        period_from=None,
        period_to=None,
        document_type="INVOICE",
        document_id="doc-1",
        document_number="INV-1",
        amount_gross=1000,
        vat_rate="20%",
        vat_amount=200,
        amount_net=800,
        counterparty_ref=None,
        contract_ref=None,
        cost_center=None,
        source_type=None,
        source_id=None,
        external_ref=None,
        provider=None,
        meta=meta or {},
    )


def test_mapping_service_applies_rule_and_updates_entry_id():
    service = ErpMappingService(db=None)
    rule = ErpMappingRule(
        id="rule-1",
        mapping_id="map-1",
        match_kind=ErpMappingMatchKind.SERVICE_CODE,
        match_value="SERVICE_A",
        gl_account="20.01",
        subaccount_1="CFO-1",
        subaccount_2=None,
        subaccount_3=None,
        cost_item="Fuel",
        vat_code="VAT20",
        counterparty_ref_mode=ErpCounterpartyRefMode.ERP_ID,
        nomenclature_ref="NOM-1",
        priority=1,
        enabled=True,
    )
    entry = _entry(meta={"service_code": "SERVICE_A"})
    mapped = service.apply_mapping([entry], [rule])[0]

    assert mapped.meta["erp_mapping"]["gl_account"] == "20.01"
    assert mapped.meta["erp_mapping"]["counterparty_ref_mode"] == "ERP_ID"
    assert mapped.entry_id == build_entry_id(mapped)


def test_mapping_service_skips_unmatched_rule():
    service = ErpMappingService(db=None)
    rule = ErpMappingRule(
        id="rule-2",
        mapping_id="map-1",
        match_kind=ErpMappingMatchKind.DOC_TYPE,
        match_value="ACT",
        gl_account="90.01",
        subaccount_1=None,
        subaccount_2=None,
        subaccount_3=None,
        cost_item=None,
        vat_code=None,
        counterparty_ref_mode=None,
        nomenclature_ref=None,
        priority=1,
        enabled=True,
    )
    entry = _entry()
    mapped = service.apply_mapping([entry], [rule])[0]
    assert mapped.meta == entry.meta
