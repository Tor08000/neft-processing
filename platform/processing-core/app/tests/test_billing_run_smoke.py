from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models.billing_period import BillingPeriod, BillingPeriodType
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.operation import Operation, OperationStatus, OperationType, ProductType


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_client(admin_auth_headers: dict):
    with TestClient(app) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


def _make_operation(
    *,
    client_id: str,
    created_at: datetime,
    captured_amount: int,
    refunded_amount: int = 0,
) -> Operation:
    operation_id = str(uuid4())
    return Operation(
        ext_operation_id=operation_id,
        operation_type=OperationType.COMMIT,
        status=OperationStatus.CAPTURED,
        created_at=created_at,
        updated_at=created_at,
        merchant_id="m-1",
        terminal_id="t-1",
        client_id=client_id,
        card_id="card-1",
        product_id="prod-1",
        product_type=ProductType.AI92,
        amount=captured_amount,
        amount_settled=captured_amount,
        currency="RUB",
        quantity=Decimal("10.000"),
        unit_price=Decimal("5.500"),
        captured_amount=captured_amount,
        refunded_amount=refunded_amount,
        response_code="00",
        response_message="OK",
        authorized=True,
    )


def test_billing_run_smoke(admin_client: TestClient, session: Session):
    client_id = str(uuid4())
    start_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)

    operations = [
        _make_operation(client_id=client_id, created_at=start_at + timedelta(hours=1), captured_amount=2_000),
        _make_operation(client_id=client_id, created_at=start_at + timedelta(hours=2), captured_amount=3_000),
    ]
    session.add_all(operations)
    session.commit()

    payload = {
        "period_type": BillingPeriodType.ADHOC.value,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "tz": "UTC",
        "client_id": None,
    }

    invoice_ids: list[str] = []
    try:
        first_response = admin_client.post("/api/v1/admin/billing/run", json=payload)
        assert first_response.status_code == 200
        first_body = first_response.json()
        assert first_body["invoices_created"] == 1
        assert first_body["invoice_lines_created"] == len(operations)
        assert first_body["total_amount"] == 5_000
        assert first_body["period_from"] == str(start_at.date())
        assert first_body["period_to"] == str(end_at.date())

        invoice = session.query(Invoice).one()
        invoice_ids.append(invoice.id)
        assert invoice.period_from == start_at.date()
        assert invoice.period_to == end_at.date()
        assert invoice.status == InvoiceStatus.DRAFT
        lines = session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()
        assert len(lines) == len(operations)
        assert sum(int(line.line_amount) for line in lines) == invoice.total_amount

        second_response = admin_client.post("/api/v1/admin/billing/run", json=payload)
        assert second_response.status_code == 200
        second_body = second_response.json()
        assert second_body["invoices_rebuilt"] == 1
        assert second_body["invoices_created"] == 0
        assert session.query(Invoice).count() == 1

        session.refresh(invoice)
        lines_after = session.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()
        assert len(lines_after) == len(operations)
        assert sum(int(line.line_amount) for line in lines_after) == invoice.total_amount
    finally:
        if not invoice_ids:
            invoice_ids = [row.id for row in session.query(Invoice.id).filter(Invoice.client_id == client_id).all()]
        if invoice_ids:
            session.query(InvoiceLine).filter(InvoiceLine.invoice_id.in_(invoice_ids)).delete(synchronize_session=False)
        session.query(Invoice).filter(Invoice.client_id == client_id).delete(synchronize_session=False)
        session.query(BillingPeriod).filter(
            BillingPeriod.start_at == start_at, BillingPeriod.end_at == end_at
        ).delete(synchronize_session=False)
        session.query(Operation).filter(Operation.client_id == client_id).delete(synchronize_session=False)
        session.commit()
