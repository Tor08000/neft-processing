from datetime import date, datetime, timezone

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.client import client_portal_user
from app.api.v1.endpoints.billing_invoices import router as billing_invoices_router
from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.finance import InvoicePayment
from app.models.invoice import Invoice, InvoicePdfStatus, InvoiceStatus
from app.models.money_flow import MoneyFlowEvent
from app.tests._scoped_router_harness import router_client_context


TEST_TABLES = (
    AuditLog.__table__,
    BillingPeriod.__table__,
    Invoice.__table__,
    InvoicePayment.__table__,
    MoneyFlowEvent.__table__,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    stub_metadata = MetaData()
    Table("clearing_batch", stub_metadata, Column("id", String(36), primary_key=True))
    Table("reconciliation_requests", stub_metadata, Column("id", String(36), primary_key=True))
    stub_metadata.create_all(bind=engine)
    for table in TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture
def client_token_claims() -> dict[str, object]:
    return {
        "sub": "client-user-1",
        "user_id": "client-user-1",
        "client_id": "client-1",
        "roles": ["CLIENT_USER"],
    }


@pytest.fixture
def client(session: Session, client_token_claims: dict[str, object]):
    def _client_portal_override() -> dict[str, object]:
        return dict(client_token_claims)

    with router_client_context(
        router=billing_invoices_router,
        db_session=session,
        dependency_overrides={client_portal_user: _client_portal_override},
    ) as scoped_client:
        yield scoped_client


def _create_invoice(session: Session, total: int, status: InvoiceStatus = InvoiceStatus.SENT) -> str:
    today = date.today()
    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=BillingPeriodStatus.FINALIZED,
    )
    session.add(period)
    session.flush()
    invoice = Invoice(
        client_id="client-1",
        period_from=today,
        period_to=today,
        currency="RUB",
        billing_period_id=period.id,
        total_amount=total,
        tax_amount=0,
        total_with_tax=total,
        amount_paid=0,
        amount_due=total,
        status=status,
        pdf_status=InvoicePdfStatus.READY,
    )
    session.add(invoice)
    session.commit()
    return str(invoice.id)


def test_invoice_payment_flow(client, session: Session):
    invoice_id = _create_invoice(session, 100)

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": 40, "external_ref": "BANK-123"},
    )

    assert response.status_code == 403
    payments = session.query(InvoicePayment).filter_by(invoice_id=invoice_id).all()
    invoice = session.query(Invoice).filter_by(id=invoice_id).one()
    assert payments == []
    assert invoice.status == InvoiceStatus.SENT
    assert invoice.amount_paid == 0
    assert invoice.amount_due == 100


def test_payment_idempotency_external_ref(client, session: Session):
    invoice_id = _create_invoice(session, 100)

    first = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": 40, "external_ref": "IDEMP-1"},
    )
    second = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": 40, "external_ref": "IDEMP-1"},
    )

    assert first.status_code == 403
    assert second.status_code == 403
    assert session.query(InvoicePayment).filter_by(invoice_id=invoice_id).count() == 0


def test_partial_then_full_payment(client, session: Session):
    invoice_id = _create_invoice(session, 100)

    partial = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": 30, "external_ref": "PART-1"},
    )
    extra = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": 10, "external_ref": "PART-3"},
    )

    assert partial.status_code == 403
    assert extra.status_code == 403
    invoice = session.query(Invoice).filter_by(id=invoice_id).one()
    assert invoice.status == InvoiceStatus.SENT
    assert invoice.amount_paid == 0
    assert invoice.amount_due == 100


def test_overpayment_rejected(client, session: Session):
    invoice_id = _create_invoice(session, 100)

    response = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": 120, "external_ref": "OVERPAY-1"},
    )

    assert response.status_code == 403
    payments = session.query(InvoicePayment).filter_by(invoice_id=invoice_id).all()
    invoice = session.query(Invoice).filter_by(id=invoice_id).one()
    assert len(payments) == 0
    assert invoice.status == InvoiceStatus.SENT
    assert invoice.amount_paid == 0
