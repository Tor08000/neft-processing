import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_CELERY", "1")
os.environ.setdefault("NEFT_S3_ENDPOINT", "http://minio:9000")
os.environ.setdefault("NEFT_S3_ACCESS_KEY", "change-me")
os.environ.setdefault("NEFT_S3_SECRET_KEY", "change-me")
os.environ.setdefault("NEFT_S3_BUCKET_INVOICES", "neft-invoices")
os.environ.setdefault("NEFT_S3_REGION", "us-east-1")

from app.db import Base, engine, get_sessionmaker
from app.main import app
from app.models.invoice import InvoiceStatus
from app.models.operation import Operation, OperationStatus, OperationType, ProductType


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_captured_operations(target_date: date, count: int = 2) -> None:
    session = get_sessionmaker()()
    base_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    for idx in range(count):
        amount = 2000 + idx * 1000
        op = Operation(
            ext_operation_id=f"pay-op-{idx}",
            operation_type=OperationType.COMMIT,
            status=OperationStatus.CAPTURED,
            created_at=base_dt + timedelta(hours=idx + 1),
            updated_at=base_dt + timedelta(hours=idx + 1),
            merchant_id="m-1",
            terminal_id="t-1",
            client_id="client-1",
            card_id="card-1",
            product_id="FUEL",
            product_type=ProductType.AI92,
            amount=amount,
            amount_settled=amount,
            currency="RUB",
            quantity=Decimal("1.0"),
            unit_price=Decimal(str(amount)),
            captured_amount=amount,
            refunded_amount=0,
            response_code="00",
            response_message="OK",
            authorized=True,
        )
        session.add(op)
    session.commit()
    session.close()


def test_invoice_payment_flow(client_auth_headers: dict):
    target_date = date.today()
    _seed_captured_operations(target_date)

    with TestClient(app) as client:
        client.headers.update(client_auth_headers)
        close_resp = client.post(
            "/api/v1/billing/close-period",
            json={"date_from": target_date.isoformat(), "date_to": target_date.isoformat(), "tenant_id": 1},
        )
        assert close_resp.status_code == 200
        batch_id = close_resp.json()["batch_id"]

        invoice_resp = client.post(
            "/api/v1/invoices/generate",
            params={"batch_id": batch_id},
        )
        assert invoice_resp.status_code == 200
        invoice_payload = invoice_resp.json()
        invoice_id = invoice_payload["invoice_id"]

        pdf_resp = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"].startswith("application/pdf")

        partial_payment = client.post(
            f"/api/v1/invoices/{invoice_id}/payments",
            json={"amount": 1500, "external_ref": "BANK-123"},
        )
        assert partial_payment.status_code == 201
        partial_payload = partial_payment.json()
        assert partial_payload["invoice_status"] == InvoiceStatus.PARTIALLY_PAID.value

        idempotent_payment = client.post(
            f"/api/v1/invoices/{invoice_id}/payments",
            json={"amount": 1500, "external_ref": "BANK-123"},
        )
        assert idempotent_payment.status_code == 201
        assert idempotent_payment.json()["payment_id"] == partial_payload["payment_id"]

        remaining_payment = client.post(
            f"/api/v1/invoices/{invoice_id}/payments",
            json={"amount": partial_payload["due_amount"], "external_ref": "BANK-124"},
        )
        assert remaining_payment.status_code == 201
        remaining_payload = remaining_payment.json()
        assert remaining_payload["invoice_status"] == InvoiceStatus.PAID.value
