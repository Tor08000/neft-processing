from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.db import Base, SessionLocal, engine
from app.integrations.onec.exporter import export_onec_documents
from app.models.audit_log import ActorType
from app.models.client import Client
from app.models.integrations import IntegrationFile, IntegrationMapping, IntegrationType
from app.models.invoice import Invoice, InvoiceLine
from app.services.audit_service import RequestContext


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_onec_export_creates_xml(db_session):
    client = Client(id=uuid4(), name="ООО НЕФТЬ", inn="7700000000")
    db_session.add(client)

    invoice = Invoice(
        id=str(uuid4()),
        client_id=str(client.id),
        number="INV-2026-000123",
        period_from=date(2026, 1, 1),
        period_to=date(2026, 1, 31),
        currency="RUB",
        total_amount=10000000,
        tax_amount=2000000,
        total_with_tax=12000000,
        amount_paid=0,
        amount_due=12000000,
    )
    line = InvoiceLine(
        invoice_id=invoice.id,
        operation_id=str(uuid4()),
        product_id="SERVICE-FUEL-CARDS",
        line_amount=invoice.total_amount,
        tax_amount=invoice.tax_amount,
    )
    db_session.add(invoice)
    db_session.add(line)

    mapping_income = IntegrationMapping(
        integration_type=IntegrationType.ONEC,
        entity_type="INVOICE_LINE",
        source_field="line.sku",
        target_field="IncomeAccount",
        transform="const:90.01",
        is_required=True,
        version="2026.01",
    )
    mapping_vat = IntegrationMapping(
        integration_type=IntegrationType.ONEC,
        entity_type="INVOICE_LINE",
        source_field="line.sku",
        target_field="VATAccount",
        transform="const:68.02",
        is_required=True,
        version="2026.01",
    )
    db_session.add(mapping_income)
    db_session.add(mapping_vat)
    db_session.commit()

    actor = RequestContext(actor_type=ActorType.SYSTEM, actor_id="tester")
    export = export_onec_documents(
        db_session,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        mapping_version="2026.01",
        seller={"name": "ООО НЕФТЬ", "inn": "7700000000", "kpp": "770001001"},
        actor=actor,
    )
    db_session.commit()

    assert export.file_id is not None
    file_record = db_session.query(IntegrationFile).filter(IntegrationFile.id == export.file_id).one()
    content = file_record.payload.decode("utf-8")
    assert "<Invoice>" in content
    assert "<Act>" in content
    assert "<IncomeAccount>90.01</IncomeAccount>" in content
