from datetime import date

import pytest

from app.db import Base, SessionLocal, engine
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerEntryDirection
from app.models.invoice import InvoicePdfStatus, InvoiceStatus
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.services.finance import FinanceService
from app.services.internal_ledger import InternalLedgerService


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_invoice_issued_posts_balanced_entries(db_session):
    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-1",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            currency="RUB",
            status=InvoiceStatus.ISSUED,
            lines=[
                BillingLineData(
                    product_id="fuel",
                    liters=None,
                    unit_price=None,
                    line_amount=1000,
                    tax_amount=200,
                )
            ],
        )
    )

    entries = db_session.query(InternalLedgerEntry).all()
    assert len(entries) == 3

    debit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.DEBIT)
    credit_sum = sum(entry.amount for entry in entries if entry.direction == InternalLedgerEntryDirection.CREDIT)
    assert debit_sum == credit_sum == invoice.total_with_tax


def test_payment_applied_is_idempotent(db_session):
    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="client-2",
            period_from=date(2024, 2, 1),
            period_to=date(2024, 2, 29),
            currency="RUB",
            status=InvoiceStatus.ISSUED,
            lines=[
                BillingLineData(
                    product_id="fuel",
                    liters=None,
                    unit_price=None,
                    line_amount=1500,
                    tax_amount=0,
                )
            ],
        )
    )
    invoice.pdf_status = InvoicePdfStatus.READY
    db_session.commit()

    repo.update_status(invoice.id, InvoiceStatus.SENT)

    service = FinanceService(db_session)
    result = service.apply_payment(
        invoice_id=invoice.id,
        amount=500,
        currency=invoice.currency,
        idempotency_key="payment:ledger-test",
        request_ctx=None,
        token=None,
    )

    entries_after_payment = db_session.query(InternalLedgerEntry).all()
    assert len(entries_after_payment) == 4

    replay = service.apply_payment(
        invoice_id=invoice.id,
        amount=500,
        currency=invoice.currency,
        idempotency_key="payment:ledger-test",
        request_ctx=None,
        token=None,
    )
    assert replay.is_replay is True
    assert db_session.query(InternalLedgerEntry).count() == 4

    payment_entries = [
        entry
        for entry in entries_after_payment
        if entry.direction in {InternalLedgerEntryDirection.DEBIT, InternalLedgerEntryDirection.CREDIT}
    ]
    sample = payment_entries[0]
    payload = {
        "tenant_id": sample.tenant_id,
        "ledger_transaction_id": str(sample.ledger_transaction_id),
        "account_id": str(sample.account_id),
        "direction": sample.direction.value,
        "amount": sample.amount,
        "currency": sample.currency,
    }
    assert sample.entry_hash == InternalLedgerService.entry_hash_for_payload(payload)
