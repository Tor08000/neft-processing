import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import csv
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_CELERY", "1")
os.environ.setdefault("NEFT_S3_ENDPOINT", "http://minio:9000")
os.environ.setdefault("NEFT_S3_ACCESS_KEY", "change-me")
os.environ.setdefault("NEFT_S3_SECRET_KEY", "change-me")
os.environ.setdefault("NEFT_S3_BUCKET_ACCOUNTING_EXPORTS", "accounting-exports")
os.environ.setdefault("NEFT_S3_REGION", "us-east-1")

from app.config import settings
from app.db import Base, engine, get_sessionmaker
from app.api.dependencies.admin import require_admin_user
from app.models.accounting_export_batch import (
    AccountingExportBatch,
    AccountingExportFormat,
    AccountingExportState,
    AccountingExportType,
)
from app.models.audit_log import ActorType, AuditLog
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import InvoicePayment, InvoiceSettlementAllocation, SettlementSourceType
from app.models.invoice import Invoice, InvoiceStatus
from app.routers.admin.accounting_exports import router as accounting_exports_router
from app.services.accounting_export_service import AccountingExportForbidden, AccountingExportService
from app.services.audit_service import RequestContext
from app.services.s3_storage import S3Storage
from app.tests._scoped_router_harness import router_client_context


class _InMemoryS3Storage:
    _objects: dict[tuple[str, str], bytes] = {}

    def __init__(self, *, bucket: str | None = None):
        self.bucket = bucket or settings.NEFT_S3_BUCKET_ACCOUNTING_EXPORTS

    def put_bytes(self, key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> str:
        self._objects[(self.bucket, key)] = payload
        return f"s3://{self.bucket}/{key}"

    def get_bytes(self, key: str) -> bytes | None:
        return self._objects.get((self.bucket, key))


class _GraphRegistryStub:
    def get_or_create_node(self, *, tenant_id, node_type, ref_id, ref_table):
        return SimpleNamespace(node=SimpleNamespace(id=f"{node_type}:{ref_id}"))

    def link_edge(self, **_kwargs) -> None:
        return None


class _LegalGraphBuilderStub:
    def __init__(self, *_args, **_kwargs):
        self.registry = _GraphRegistryStub()

    def ensure_accounting_export_graph(self, *_args, **_kwargs) -> None:
        return None


@pytest.fixture(autouse=True)
def _stub_export_sidecars(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import accounting_export_service as accounting_export_service
    from app.services.decision import DecisionOutcome

    _InMemoryS3Storage._objects = {}
    monkeypatch.setattr(accounting_export_service, "S3Storage", _InMemoryS3Storage)
    monkeypatch.setattr(accounting_export_service, "LegalGraphBuilder", _LegalGraphBuilderStub)
    monkeypatch.setattr("app.tests.test_accounting_exports.S3Storage", _InMemoryS3Storage)
    monkeypatch.setattr(
        accounting_export_service.DecisionEngine,
        "evaluate",
        lambda *_args, **_kwargs: SimpleNamespace(outcome=DecisionOutcome.ALLOW),
    )


@pytest.fixture(autouse=True)
def clean_db():
    tables = [
        AccountingExportBatch.__table__,
        AuditLog.__table__,
        BillingPeriod.__table__,
        Invoice.__table__,
        InvoicePayment.__table__,
        InvoiceSettlementAllocation.__table__,
    ]
    Base.metadata.drop_all(bind=engine, tables=tables)
    Base.metadata.create_all(bind=engine, tables=tables)
    yield
    Base.metadata.drop_all(bind=engine, tables=tables)


def _make_period(*, status: BillingPeriodStatus, day_offset: int = 0) -> BillingPeriod:
    period_start = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_offset)
    period_end = datetime(2024, 1, 31, tzinfo=timezone.utc) + timedelta(days=day_offset)
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
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}
    with pytest.raises(AccountingExportForbidden):
        service.create_export(
            period_id=str(period.id),
            export_type=AccountingExportType.CHARGES,
            export_format=AccountingExportFormat.CSV,
            request_ctx=_request_ctx(),
            token=token,
        )

    finalized = _make_period(status=BillingPeriodStatus.FINALIZED, day_offset=31)
    session.add(finalized)
    session.commit()

    batch = service.create_export(
        period_id=str(finalized.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        token=token,
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
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}
    batch_v1 = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=1,
        token=token,
    )
    batch_v2 = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=2,
        token=token,
    )

    batch_v1 = service.generate_export(batch_id=batch_v1.id, request_ctx=_request_ctx(), token=token)
    batch_v2 = service.generate_export(batch_id=batch_v2.id, request_ctx=_request_ctx(), token=token)
    session.commit()

    storage = S3Storage(bucket=settings.NEFT_S3_BUCKET_ACCOUNTING_EXPORTS)
    payload_v1 = storage.get_bytes(batch_v1.object_key)
    payload_v2 = storage.get_bytes(batch_v2.object_key)
    rows_v1 = list(csv.reader(payload_v1.decode("utf-8").splitlines(), delimiter=";"))
    rows_v2 = list(csv.reader(payload_v2.decode("utf-8").splitlines(), delimiter=";"))
    for rows in (rows_v1, rows_v2):
        for row in rows[2:]:
            row[0] = "<batch>"
    assert rows_v1 == rows_v2
    assert batch_v1.checksum_sha256 != batch_v2.checksum_sha256
    assert rows_v1[2][1] == rows_v2[2][1]
    session.close()


def test_accounting_export_idempotency():
    session = get_sessionmaker()()
    period = _make_period(status=BillingPeriodStatus.FINALIZED)
    session.add(period)
    session.commit()

    service = AccountingExportService(session)
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}
    first = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=1,
        token=token,
    )
    second = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=1,
        token=token,
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
    settlement_period.start_at = settlement_period.start_at + timedelta(days=31)
    settlement_period.end_at = settlement_period.end_at + timedelta(days=31)
    if settlement_period.finalized_at is not None:
        settlement_period.finalized_at = settlement_period.finalized_at + timedelta(days=31)
    if settlement_period.locked_at is not None:
        settlement_period.locked_at = settlement_period.locked_at + timedelta(days=31)
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
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}
    batch = service.create_export(
        period_id=str(settlement_period.id),
        export_type=AccountingExportType.SETTLEMENT,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        version=1,
        token=token,
    )
    batch = service.generate_export(batch_id=batch.id, request_ctx=_request_ctx(), token=token)
    session.commit()

    storage = S3Storage(bucket=settings.NEFT_S3_BUCKET_ACCOUNTING_EXPORTS)
    payload = storage.get_bytes(batch.object_key)
    assert payload is not None

    rows = list(csv.reader(payload.decode("utf-8").splitlines(), delimiter=";"))
    assert rows[0] == ["# minor_units=2"]
    assert rows[1] == [
        "batch_id",
        "entry_id",
        "tenant_id",
        "client_id",
        "posting_date",
        "document_id",
        "document_number",
        "source_type",
        "source_id",
        "provider",
        "external_ref",
        "currency",
        "amount_gross",
        "charge_period_from",
        "charge_period_to",
        "contract_ref",
        "counterparty_ref",
    ]
    assert rows[2][5] == invoice.id
    assert rows[2][7] == "PAYMENT"
    assert rows[2][9] == "bank"
    assert rows[2][10] == "payment-1"
    session.close()


def test_accounting_export_confirm_allows_finance_role():
    session = get_sessionmaker()()
    period = _make_period(status=BillingPeriodStatus.FINALIZED)
    session.add(period)
    session.commit()

    service = AccountingExportService(session)
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}
    batch = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        token=token,
    )
    session.commit()

    with router_client_context(
        router=accounting_exports_router,
        prefix="/api/v1/admin",
        db_session=session,
        dependency_overrides={require_admin_user: lambda: token},
    ) as client:
        response = client.post(
            f"/api/v1/admin/accounting/exports/{batch.id}/confirm",
            json={
                "erp_system": "1C",
                "erp_import_id": "import-1",
                "status": "CONFIRMED",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert response.status_code == 200
    session.close()


def test_accounting_export_confirm_idempotent():
    session = get_sessionmaker()()
    period = _make_period(status=BillingPeriodStatus.FINALIZED)
    session.add(period)
    session.commit()

    service = AccountingExportService(session)
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}
    batch = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        token=token,
    )
    session.commit()

    processed_at = datetime.now(timezone.utc)
    batch = service.confirm_export(
        batch_id=batch.id,
        request_ctx=_request_ctx(),
        erp_system="SAP",
        erp_import_id="sap-1",
        status="CONFIRMED",
        processed_at=processed_at,
        token=token,
    )
    session.commit()

    repeat = service.confirm_export(
        batch_id=batch.id,
        request_ctx=_request_ctx(),
        erp_system="SAP",
        erp_import_id="sap-1",
        status="CONFIRMED",
        processed_at=processed_at,
        token=token,
    )
    assert repeat.id == batch.id
    assert repeat.state == AccountingExportState.CONFIRMED
    session.close()


def test_accounting_export_reject_marks_failed():
    session = get_sessionmaker()()
    period = _make_period(status=BillingPeriodStatus.FINALIZED)
    session.add(period)
    session.commit()

    service = AccountingExportService(session)
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}
    batch = service.create_export(
        period_id=str(period.id),
        export_type=AccountingExportType.CHARGES,
        export_format=AccountingExportFormat.CSV,
        request_ctx=_request_ctx(),
        token=token,
    )
    session.commit()

    rejected = service.confirm_export(
        batch_id=batch.id,
        request_ctx=_request_ctx(),
        erp_system="1C",
        erp_import_id="reject-1",
        status="REJECTED",
        message="format_error",
        processed_at=datetime.now(timezone.utc),
        token=token,
    )
    assert rejected.state == AccountingExportState.FAILED
    assert rejected.error_message == "format_error"
    session.close()
