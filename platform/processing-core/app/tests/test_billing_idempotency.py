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
from app.models.clearing_batch import ClearingBatch
from app.models.invoice import Invoice
from app.models.operation import Operation, OperationStatus, OperationType, ProductType
from app.services.s3_storage import S3Storage


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_captured_operations(target_date: date, count: int = 3) -> None:
    session = get_sessionmaker()()
    base_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    for idx in range(count):
        amount = 900 + idx * 100
        op = Operation(
            ext_operation_id=f"idem-op-{idx}",
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


def test_billing_idempotency_close_period():
    target_date = date.today()
    _seed_captured_operations(target_date)

    with TestClient(app) as client:
        payload = {"from": target_date.isoformat(), "to": target_date.isoformat(), "tenant_id": 1}
        resp_first = client.post("/api/v1/billing/close-period", json=payload)
        resp_second = client.post("/api/v1/billing/close-period", json=payload)

    assert resp_first.status_code == 200
    assert resp_second.status_code == 200
    assert resp_first.json()["batch_id"] == resp_second.json()["batch_id"]

    session = get_sessionmaker()()
    try:
        batches = (
            session.query(ClearingBatch)
            .filter(ClearingBatch.tenant_id == 1)
            .filter(ClearingBatch.date_from == target_date)
            .filter(ClearingBatch.date_to == target_date)
            .all()
        )
        assert len(batches) == 1
    finally:
        session.close()


def test_invoice_generate_idempotency():
    target_date = date.today()
    _seed_captured_operations(target_date)

    with TestClient(app) as client:
        batch_resp = client.post(
            "/api/v1/billing/close-period",
            json={"from": target_date.isoformat(), "to": target_date.isoformat(), "tenant_id": 1},
        )
        batch_id = batch_resp.json()["batch_id"]

        first = client.post("/api/v1/invoices/generate", params={"batch_id": batch_id})
        second = client.post("/api/v1/invoices/generate", params={"batch_id": batch_id})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["invoice_id"] == second.json()["invoice_id"]

    session = get_sessionmaker()()
    try:
        invoices = session.query(Invoice).filter(Invoice.clearing_batch_id == batch_id).all()
        assert len(invoices) == 1
        assert invoices[0].number
    finally:
        session.close()


def test_pdf_idempotency_single_object():
    target_date = date.today()
    _seed_captured_operations(target_date)

    with TestClient(app) as client:
        batch_resp = client.post(
            "/api/v1/billing/close-period",
            json={"from": target_date.isoformat(), "to": target_date.isoformat(), "tenant_id": 1},
        )
        batch_id = batch_resp.json()["batch_id"]

        first = client.post("/api/v1/invoices/generate", params={"batch_id": batch_id})
        first_invoice_id = first.json()["invoice_id"]
        first_invoice = client.get(f"/api/v1/invoices/{first_invoice_id}").json()
        first_key = first_invoice["pdf_object_key"]

        second = client.post("/api/v1/invoices/generate", params={"batch_id": batch_id})
        second_invoice_id = second.json()["invoice_id"]
        second_invoice = client.get(f"/api/v1/invoices/{second_invoice_id}").json()
        second_key = second_invoice["pdf_object_key"]

    assert first_key == second_key

    storage = S3Storage()
    assert storage.exists(first_key)
    prefix = first_key.removesuffix(".pdf")
    keys = storage.list_keys(prefix)
    assert keys == [first_key]
