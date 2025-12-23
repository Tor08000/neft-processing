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
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.s3_storage import S3Storage


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_captured_operations(target_date: date, count: int = 6) -> None:
    session = get_sessionmaker()()
    base_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    for idx in range(count):
        amount = 1000 + idx * 100
        op = Operation(
            ext_operation_id=f"seed-op-{idx}",
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


def test_billing_to_pdf_e2e():
    target_date = date.today()
    _seed_captured_operations(target_date)

    with TestClient(app) as client:
        close_resp = client.post(
            "/api/v1/billing/close-period",
            json={"from": target_date.isoformat(), "to": target_date.isoformat(), "tenant_id": 1},
        )
        assert close_resp.status_code == 200
        batch_payload = close_resp.json()
        assert batch_payload["txn_count"] == 6
        assert batch_payload["total_amount"] > 0

        invoice_resp = client.post(
            "/api/v1/invoices/generate",
            params={"batch_id": batch_payload["batch_id"]},
        )
        assert invoice_resp.status_code == 200
        invoice_payload = invoice_resp.json()
        assert invoice_payload["state"] == "ISSUED"

        invoice_get = client.get(f"/api/v1/invoices/{invoice_payload['invoice_id']}")
        assert invoice_get.status_code == 200
        invoice_data = invoice_get.json()
        assert invoice_data["pdf_url"]

        storage = S3Storage()
        assert invoice_data["pdf_object_key"]
        assert storage.exists(invoice_data["pdf_object_key"])
