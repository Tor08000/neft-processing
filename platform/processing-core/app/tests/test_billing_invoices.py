from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.db import Base, SessionLocal, engine
from app.models.client import Client
from app.models.invoice import InvoiceStatus, Invoice
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.services.billing_service import generate_invoices_for_period


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_operation(**kwargs) -> Operation:
    now = kwargs.pop("created_at", datetime.utcnow())
    return Operation(
        ext_operation_id=f"ext-{now.timestamp()}",
        operation_type=kwargs.pop("operation_type", OperationType.COMMIT),
        status=kwargs.pop("status", OperationStatus.COMPLETED),
        created_at=now,
        updated_at=now,
        merchant_id=kwargs.pop("merchant_id", "m1"),
        terminal_id=kwargs.pop("terminal_id", "t1"),
        client_id=kwargs.pop("client_id", "c1"),
        card_id=kwargs.pop("card_id", "card1"),
        product_id=kwargs.pop("product_id", "p1"),
        product_type=kwargs.pop("product_type", ProductType.AI95),
        amount=kwargs.pop("amount", 1000),
        currency=kwargs.pop("currency", "RUB"),
        quantity=kwargs.pop("quantity", Decimal("1.000")),
        unit_price=kwargs.pop("unit_price", Decimal("50.000")),
        captured_amount=kwargs.pop("captured_amount", 0),
        refunded_amount=kwargs.pop("refunded_amount", 0),
        response_code="00",
        response_message="OK",
        authorized=True,
    )


def test_create_invoice_totals(session):
    repo = BillingRepository(session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-1",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            currency="RUB",
            status=InvoiceStatus.ISSUED,
            lines=[
                BillingLineData(
                    product_id="p1",
                    liters=Decimal("10.000"),
                    unit_price=Decimal("50.000"),
                    line_amount=5000,
                    tax_amount=1000,
                ),
                BillingLineData(
                    product_id="p2",
                    liters=None,
                    unit_price=None,
                    line_amount=2500,
                    tax_amount=0,
                ),
            ],
            external_number="INV-1",
        )
    )

    assert invoice.total_amount == 7500
    assert invoice.tax_amount == 1000
    assert invoice.total_with_tax == 8500
    assert invoice.status == InvoiceStatus.ISSUED
    assert len(invoice.lines) == 2


def test_update_status(session):
    repo = BillingRepository(session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-2",
            period_from=date(2024, 2, 1),
            period_to=date(2024, 2, 28),
            currency="RUB",
            lines=[BillingLineData(product_id="p1", liters=None, unit_price=None, line_amount=1000, tax_amount=0)],
        )
    )

    paid_at = datetime.utcnow()
    updated = repo.update_status(invoice.id, InvoiceStatus.PAID, paid_at=paid_at)

    assert updated is not None
    assert updated.status == InvoiceStatus.PAID
    assert updated.paid_at == paid_at


def test_generate_invoices_for_period(session):
    client1 = Client(name="Client 1", tariff_plan="standard")
    client2 = Client(name="Client 2", tariff_plan="standard")
    session.add_all([client1, client2])
    session.flush()

    period_start = date(2024, 3, 1)
    period_end = date(2024, 3, 31)
    base_time = datetime.combine(period_start, datetime.min.time()) + timedelta(hours=10)

    ops = [
        make_operation(client_id=str(client1.id), amount=2000, created_at=base_time),
        make_operation(client_id=str(client1.id), amount=3000, created_at=base_time + timedelta(days=1)),
        make_operation(client_id=str(client2.id), amount=1500, created_at=base_time + timedelta(days=2)),
    ]
    session.add_all(ops)
    session.commit()

    generated = generate_invoices_for_period(
        session, period_from=period_start, period_to=period_end, status=InvoiceStatus.ISSUED, options={"tax_rate": 0}
    )

    assert len(generated) == 2

    total_invoices = session.query(Invoice).all()
    assert len(total_invoices) == 2

    # Idempotency check
    generated_again = generate_invoices_for_period(
        session, period_from=period_start, period_to=period_end, status=InvoiceStatus.ISSUED, options={"tax_rate": 0}
    )
    assert len(generated_again) == 0

    amounts = sorted(invoice.total_amount for invoice in total_invoices)
    assert amounts == [1500, 5000]
    assert all(invoice.status == InvoiceStatus.ISSUED for invoice in total_invoices)
