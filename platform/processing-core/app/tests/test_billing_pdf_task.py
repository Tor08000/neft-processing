from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from sqlalchemy import Column, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.models.billing_task_link import BillingTaskLink, BillingTaskStatus, BillingTaskType
from app.models.invoice import Invoice, InvoicePdfStatus
from app.tasks.billing_pdf import generate_invoice_pdf


class DummyPdfService:
    def __init__(self, db):
        self.db = db

    def generate(self, invoice: Invoice, *, force: bool = False) -> Invoice:
        invoice.pdf_status = InvoicePdfStatus.READY
        invoice.pdf_url = f"s3://bucket/{invoice.id}/v{invoice.pdf_version or 1}.pdf"
        invoice.pdf_hash = "hash"
        invoice.pdf_generated_at = datetime.now(timezone.utc)
        invoice.pdf_version = (invoice.pdf_version or 1) + 1 if force else (invoice.pdf_version or 1)
        self.db.add(invoice)
        return invoice


class DummyTask:
    def __init__(self, task_id: str):
        self.request = SimpleNamespace(id=task_id, retries=0)

    def retry(self, exc=None, countdown=None):  # noqa: ANN001
        raise exc


def _ensure_stub_table(name: str) -> Table:
    existing = Base.metadata.tables.get(name)
    if existing is not None:
        return existing
    return Table(name, Base.metadata, Column("id", String(36), primary_key=True))


def _make_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            _ensure_stub_table("billing_periods"),
            _ensure_stub_table("clearing_batch"),
            _ensure_stub_table("reconciliation_requests"),
            Invoice.__table__,
            BillingJobRun.__table__,
            BillingTaskLink.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr("app.tasks.billing_pdf.get_sessionmaker", lambda: SessionLocal)
    return SessionLocal, engine


def _patch_dependencies(monkeypatch):
    monkeypatch.setattr("app.tasks.billing_pdf.InvoicePdfService", DummyPdfService)


def test_generate_invoice_pdf_marks_ready(monkeypatch):
    SessionLocal, engine = _make_session(monkeypatch)
    session = SessionLocal()
    try:
        _patch_dependencies(monkeypatch)
        invoice = Invoice(
            client_id="client-1",
            period_from=date(2024, 5, 1),
            period_to=date(2024, 5, 31),
            currency="RUB",
            total_amount=1000,
            tax_amount=0,
            total_with_tax=1000,
            pdf_status=InvoicePdfStatus.NONE,
        )
        session.add(invoice)
        session.commit()

        task = DummyTask("task-1")
        result = generate_invoice_pdf.run.__func__(task, invoice.id, correlation_id="corr-1")

        session.expire_all()
        refreshed = session.query(Invoice).filter_by(id=invoice.id).one()
        link = session.query(BillingTaskLink).filter_by(task_id="task-1").one()
        job = session.query(BillingJobRun).filter_by(celery_task_id="task-1").one()

        assert result["pdf_status"] == InvoicePdfStatus.READY
        assert refreshed.pdf_status == InvoicePdfStatus.READY
        assert refreshed.pdf_url
        assert refreshed.pdf_version == 1
        assert link.status == BillingTaskStatus.SUCCESS
        assert link.task_type == BillingTaskType.PDF_GENERATE
        assert job.status == BillingJobStatus.SUCCESS
        assert job.job_type == BillingJobType.PDF_GENERATE
    finally:
        session.close()
        engine.dispose()


def test_generate_invoice_pdf_skip_when_ready(monkeypatch):
    SessionLocal, engine = _make_session(monkeypatch)
    session = SessionLocal()
    try:
        _patch_dependencies(monkeypatch)
        invoice = Invoice(
            client_id="client-1",
            period_from=date(2024, 5, 1),
            period_to=date(2024, 5, 31),
            currency="RUB",
            total_amount=1000,
            tax_amount=0,
            total_with_tax=1000,
            pdf_status=InvoicePdfStatus.READY,
            pdf_version=2,
        )
        session.add(invoice)
        session.commit()

        task = DummyTask("task-2")
        result = generate_invoice_pdf.run.__func__(task, invoice.id, correlation_id="corr-2")

        refreshed = session.query(Invoice).filter_by(id=invoice.id).one()
        job = session.query(BillingJobRun).filter_by(celery_task_id="task-2").one()

        assert result["pdf_status"] == InvoicePdfStatus.READY
        assert refreshed.pdf_version == 2
        assert job.status == BillingJobStatus.SUCCESS
        assert job.metrics.get("skipped") is True
    finally:
        session.close()
        engine.dispose()


def test_generate_invoice_pdf_force_regenerates(monkeypatch):
    SessionLocal, engine = _make_session(monkeypatch)
    session = SessionLocal()
    try:
        _patch_dependencies(monkeypatch)
        invoice = Invoice(
            client_id="client-1",
            period_from=date(2024, 5, 1),
            period_to=date(2024, 5, 31),
            currency="RUB",
            total_amount=1000,
            tax_amount=0,
            total_with_tax=1000,
            pdf_status=InvoicePdfStatus.READY,
            pdf_version=1,
        )
        session.add(invoice)
        session.commit()

        task = DummyTask("task-3")
        result = generate_invoice_pdf.run.__func__(task, invoice.id, correlation_id="corr-3", force=True)

        session.expire_all()
        refreshed = session.query(Invoice).filter_by(id=invoice.id).one()

        assert result["pdf_status"] == InvoicePdfStatus.READY
        assert refreshed.pdf_version == 2
        assert refreshed.pdf_hash == "hash"
    finally:
        session.close()
        engine.dispose()
