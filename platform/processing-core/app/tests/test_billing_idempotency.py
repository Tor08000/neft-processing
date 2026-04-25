from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.v1.endpoints.billing_invoices as billing_endpoints
import app.services.billing_invoice_service as billing_invoice_service
from app.api.v1.endpoints.billing_invoices import router as billing_router
from app.db import Base, get_db
from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod
from app.models.clearing_batch import ClearingBatch
from app.models.finance import InvoiceSettlementAllocation
from app.models.invoice import Invoice, InvoicePdfStatus
from app.models.operation import Operation, OperationStatus, OperationType, ProductType

os.environ.setdefault("DISABLE_CELERY", "1")


class _AllowDecisionEngine:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def evaluate(self, _ctx):
        return type("Decision", (), {"outcome": billing_invoice_service.DecisionOutcome.ALLOW})()


class _NoopGraphBuilder:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def ensure_invoice_graph(self, *args, **kwargs) -> None:
        return None


class _MemoryInvoiceStorage:
    _objects: dict[str, bytes] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    @classmethod
    def reset(cls) -> None:
        cls._objects = {}

    def ensure_bucket(self) -> None:
        return None

    def put_bytes(self, object_key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> str:
        self._objects[object_key] = payload
        return self.public_url(object_key)

    def exists(self, object_key: str) -> bool:
        return object_key in self._objects

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(key for key in self._objects if key.startswith(prefix))

    def get_bytes(self, object_key: str) -> bytes | None:
        return self._objects.get(object_key)

    def public_url(self, object_key: str) -> str:
        return f"https://test-s3.local/{object_key}"


class _MemoryInvoicePdfService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = _MemoryInvoiceStorage()

    def generate(self, invoice: Invoice, *, force: bool = False) -> Invoice:
        key = invoice.pdf_object_key or f"invoices/{invoice.id}.pdf"
        payload = b"%PDF-1.4 test invoice pdf%"
        invoice.pdf_status = InvoicePdfStatus.READY
        invoice.pdf_generated_at = datetime.now(timezone.utc)
        invoice.pdf_hash = hashlib.sha256(payload).hexdigest()
        invoice.pdf_object_key = key
        invoice.pdf_url = self.storage.put_bytes(key, payload, content_type="application/pdf")
        self.db.add(invoice)
        return invoice


@pytest.fixture()
def billing_idempotency_context(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(billing_invoice_service, "DecisionEngine", _AllowDecisionEngine)
    monkeypatch.setattr(billing_invoice_service, "LegalGraphBuilder", _NoopGraphBuilder)
    monkeypatch.setattr(billing_invoice_service, "InvoicePdfService", _MemoryInvoicePdfService)
    monkeypatch.setattr(billing_endpoints, "S3Storage", _MemoryInvoiceStorage)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    if "fuel_stations" not in Base.metadata.tables:
        Table("fuel_stations", Base.metadata, Column("id", String(36), primary_key=True), extend_existing=True)
    if "reconciliation_requests" not in Base.metadata.tables:
        Table(
            "reconciliation_requests",
            Base.metadata,
            Column("id", String(36), primary_key=True),
            extend_existing=True,
        )

    Base.metadata.create_all(
        bind=engine,
        tables=[
            BillingPeriod.__table__,
            ClearingBatch.__table__,
            Operation.__table__,
            Invoice.__table__,
            InvoiceSettlementAllocation.__table__,
            AuditLog.__table__,
        ],
    )

    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    local_app = FastAPI()
    local_app.include_router(billing_router)
    local_app.dependency_overrides[get_db] = override_get_db

    _MemoryInvoiceStorage.reset()
    try:
        with TestClient(local_app) as api_client:
            yield session_factory, api_client
    finally:
        local_app.dependency_overrides.clear()
        _MemoryInvoiceStorage.reset()
        engine.dispose()


def _seed_captured_operations(session_factory: sessionmaker[Session], *, target_date: date, count: int = 3) -> None:
    session = session_factory()
    try:
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
    finally:
        session.close()


def test_billing_idempotency_close_period(billing_idempotency_context):
    session_factory, client = billing_idempotency_context
    target_date = date.today()
    _seed_captured_operations(session_factory, target_date=target_date)

    payload = {"date_from": target_date.isoformat(), "date_to": target_date.isoformat(), "tenant_id": 1}
    resp_first = client.post("/api/v1/billing/close-period", json=payload)
    resp_second = client.post("/api/v1/billing/close-period", json=payload)

    assert resp_first.status_code == 200
    assert resp_second.status_code == 200
    assert resp_first.json()["batch_id"] == resp_second.json()["batch_id"]

    with session_factory() as session:
        batches = (
            session.query(ClearingBatch)
            .filter(ClearingBatch.tenant_id == 1)
            .filter(ClearingBatch.date_from == target_date)
            .filter(ClearingBatch.date_to == target_date)
            .all()
        )
        assert len(batches) == 1


def test_close_period_requires_date_fields(billing_idempotency_context):
    session_factory, client = billing_idempotency_context
    target_date = date.today()
    _seed_captured_operations(session_factory, target_date=target_date)

    response = client.post(
        "/api/v1/billing/close-period",
        json={"from": target_date.isoformat(), "to": target_date.isoformat(), "tenant_id": 1},
    )

    assert response.status_code == 422


def test_invoice_generate_idempotency(billing_idempotency_context):
    session_factory, client = billing_idempotency_context
    target_date = date.today()
    _seed_captured_operations(session_factory, target_date=target_date)

    batch_resp = client.post(
        "/api/v1/billing/close-period",
        json={"date_from": target_date.isoformat(), "date_to": target_date.isoformat(), "tenant_id": 1},
    )
    batch_id = batch_resp.json()["batch_id"]

    first = client.post("/api/v1/invoices/generate", params={"batch_id": batch_id})
    second = client.post("/api/v1/invoices/generate", params={"batch_id": batch_id})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["invoice_id"] == second.json()["invoice_id"]

    with session_factory() as session:
        invoices = session.query(Invoice).filter(Invoice.clearing_batch_id == batch_id).all()
        assert len(invoices) == 1
        assert invoices[0].number


def test_pdf_idempotency_single_object(billing_idempotency_context):
    session_factory, client = billing_idempotency_context
    target_date = date.today()
    _seed_captured_operations(session_factory, target_date=target_date)

    batch_resp = client.post(
        "/api/v1/billing/close-period",
        json={"date_from": target_date.isoformat(), "date_to": target_date.isoformat(), "tenant_id": 1},
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

    storage = _MemoryInvoiceStorage()
    assert storage.exists(first_key)
    prefix = first_key.removesuffix(".pdf")
    keys = storage.list_keys(prefix)
    assert keys == [first_key]
