import os
from datetime import datetime, timezone
from uuid import uuid4

import csv
import pytest

os.environ.setdefault("DISABLE_CELERY", "1")
os.environ.setdefault("NEFT_S3_ENDPOINT", "http://minio:9000")
os.environ.setdefault("NEFT_S3_ACCESS_KEY", "change-me")
os.environ.setdefault("NEFT_S3_SECRET_KEY", "change-me")
os.environ.setdefault("NEFT_S3_BUCKET_ACCOUNTING_EXPORTS", "accounting-exports")
os.environ.setdefault("NEFT_S3_REGION", "us-east-1")

from app.config import settings
from app.db import Base, engine, get_sessionmaker
from app.models.accounting_export_batch import AccountingExportFormat, AccountingExportType
from app.models.audit_log import ActorType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice, InvoiceStatus
from app.services.accounting_export_service import AccountingExportForbidden, AccountingExportService
from app.services.audit_service import RequestContext
from app.services.s3_storage import S3Storage


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _make_period(*, status: BillingPeriodStatus) -> BillingPeriod:
    period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)
    period = BillingPeriod(
        id=str(uuid4()),
        period_type=BillingPeriodType.ADHOC,
        start_at=period_start,
        end_at=period_end,
        tz="UTC",
        status=status,
        finalized_at=period_start if status != BillingPeriodStatus.OPEN else None,
        locked_at=period_start if status == BillingPeriodStatus.LOCKED else None,
    )
    return period


def _request_ctx() -> RequestContext:
    return RequestContext(actor_type=ActorType.SERVICE, actor_id="test", tenant_id=1)


def test_accounting_export_gating_requires_finalized_period():
    session = get_sessionmaker()()
    period = _make_period(status=BillingPeriodStatus.OPEN)
    session.add(period)
    session.commit()

    service = AccountingExportService(session)
    with pytest.raises(AccountingExportForbidden):
        service.create_export(
            period_id=str(period.id),
            export_type=AccountingExportType.CHARGES,
            export_format=AccountingExportFormat.CSV,
            request_ctx=_request_ctx(),
        )

    finalized = _make_period(status=BillingPeriodStatus.FINALIZED)
    session.add(finalized)
    session.commit()

    batch = service.create_export(
        period_id=str(finalized.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
    )
    assert batch.state.value == "CREATED"
    session.close()


def test_accounting_export_determinism_same_input():
    session = get_sessionmaker()()
    period = _make_period(status=BillingPeriodStatus.FINALIZED)
    session.add(period)
    invoice = Invoice(
        id=str(uuid4()),
        client_id="client-1",
        number="INV-001",
        period_from=period.start_at.date(),
        period_to=period.end_at.date(),
        currency="RUB",
        billing_period_id=period.id,
        total_amount=1000,
        tax_amount=200,
        total_with_tax=1200,
        amount_paid=0,
        amount_due=1200,
        status=InvoiceStatus.ISSUED,
        issued_at=period.start_at,
    )
    session.add(invoice)
    session.commit()

    service = AccountingExportService(session)
    batch_v1 = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=1,
    )
    batch_v2 = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=2,
    )

    batch_v1 = service.generate_export(batch_id=batch_v1.id, request_ctx=_request_ctx())
    batch_v2 = service.generate_export(batch_id=batch_v2.id, request_ctx=_request_ctx())
    session.commit()

    storage = S3Storage(bucket=settings.NEFT_S3_BUCKET_ACCOUNTING_EXPORTS)
    payload_v1 = storage.get_bytes(batch_v1.object_key)
    payload_v2 = storage.get_bytes(batch_v2.object_key)
    assert payload_v1 == payload_v2
    assert batch_v1.checksum_sha256 == batch_v2.checksum_sha256
    session.close()


def test_accounting_export_idempotency():
    session = get_sessionmaker()()
    period = _make_period(status=BillingPeriodStatus.FINALIZED)
    session.add(period)
    session.commit()

    service = AccountingExportService(session)
    first = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=1,
    )
    second = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=1,
    )
    session.commit()

    assert first.id == second.id
    assert session.query(type(first)).count() == 1
    session.close()


def test_accounting_export_settlement_csv_fields():
    session = get_sessionmaker()()
    charge_period = _make_period(status=BillingPeriodStatus.FINALIZED)
    settlement_period = _make_period(status=BillingPeriodStatus.FINALIZED)
    settlement_period.id = str(uuid4())
    session.add_all([charge_period, settlement_period])

    invoice = Invoice(
        id=str(uuid4()),
        client_id="client-2",
        number="INV-SET-1",
        period_from=charge_period.start_at.date(),
        period_to=charge_period.end_at.date(),
        currency="RUB",
        billing_period_id=charge_period.id,
        total_amount=1500,
        tax_amount=300,
        total_with_tax=1800,
        amount_paid=1500,
        amount_due=0,
        status=InvoiceStatus.PAID,
        issued_at=charge_period.start_at,
    )
    payment = InvoicePayment(
        id=str(uuid4()),
        invoice_id=invoice.id,
        amount=1500,
        currency="RUB",
        provider="bank",
        external_ref="payment-1",
        idempotency_key="payment-1",
    )
    allocation = InvoiceSettlementAllocation(
        id=str(uuid4()),
        invoice_id=invoice.id,
        tenant_id=1,
        client_id=invoice.client_id,
        settlement_period_id=settlement_period.id,
        source_type=SettlementSourceType.PAYMENT,
        source_id=payment.id,
        amount=1500,
        currency="RUB",
        applied_at=settlement_period.start_at,
    )
    session.add_all([invoice, payment, allocation])
    session.commit()

    service = AccountingExportService(session)
    batch = service.create_export(
        period_id=str(settlement_period.id),
        export_type=AccountingExportType.SETTLEMENT,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=1,
    )
    batch = service.generate_export(batch_id=batch.id, request_ctx=_request_ctx())
    session.commit()

    storage = S3Storage(bucket=settings.NEFT_S3_BUCKET_ACCOUNTING_EXPORTS)
    payload = storage.get_bytes(batch.object_key)
    assert payload is not None

    rows = list(csv.reader(payload.decode("utf-8").splitlines()))
    assert rows[0] == [
        "settlement_period_id",
        "invoice_id",
        "source_type",
        "source_id",
        "amount",
        "currency",
        "applied_at",
        "charge_period_id",
        "provider",
        "external_ref",
    ]
    assert rows[1][0] == str(settlement_period.id)
    assert rows[1][1] == invoice.id
    assert rows[1][2] == "PAYMENT"
    assert rows[1][8] == "bank"
    assert rows[1][9] == "payment-1"
    session.close()
