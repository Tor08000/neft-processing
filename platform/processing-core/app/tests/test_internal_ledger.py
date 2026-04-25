from datetime import date, datetime, timezone

import pytest

from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.invoice import InvoicePdfStatus, InvoiceStatus
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.services.finance import FinanceService
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService
from app.tests._finance_test_harness import finance_invariant_session_context, seed_default_finance_thresholds


ADMIN_FINANCE_TOKEN = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "ledger-tester"}


@pytest.fixture(autouse=True)
def _disable_legal_graph(monkeypatch: pytest.MonkeyPatch):
    class _NoopGraphBuilder:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ensure_settlement_allocation_graph(self, *args, **kwargs) -> None:
            return None

    monkeypatch.setattr("app.services.finance.LegalGraphBuilder", _NoopGraphBuilder)


@pytest.fixture
def db_session():
    with finance_invariant_session_context() as session:
        seed_default_finance_thresholds(session)
        yield session


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

    invoice = repo.update_status(invoice.id, InvoiceStatus.SENT)
    period = db_session.get(BillingPeriod, invoice.billing_period_id)
    assert period is not None
    period.status = BillingPeriodStatus.FINALIZED
    period.finalized_at = datetime.now(timezone.utc)
    db_session.commit()

    service = FinanceService(db_session)
    result = service.apply_payment(
        invoice_id=invoice.id,
        amount=500,
        currency=invoice.currency,
        idempotency_key="payment:ledger-test",
        request_ctx=None,
        token=ADMIN_FINANCE_TOKEN,
    )

    entries_after_payment = db_session.query(InternalLedgerEntry).all()
    assert len(entries_after_payment) == 4

    replay = service.apply_payment(
        invoice_id=invoice.id,
        amount=500,
        currency=invoice.currency,
        idempotency_key="payment:ledger-test",
        request_ctx=None,
        token=ADMIN_FINANCE_TOKEN,
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


def test_custom_transaction_currency_isolation(db_session):
    service = InternalLedgerService(db_session)
    with pytest.raises(ValueError, match="mixed currencies"):
        service.post_transaction(
            tenant_id=1,
            transaction_type=InternalLedgerTransactionType.ACCOUNTING_EXPORT_CONFIRMED,
            external_ref_type="TEST",
            external_ref_id="ref-1",
            idempotency_key="tx:currency",
            posted_at=None,
            meta=None,
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id="client-1",
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=100,
                    currency="RUB",
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_CASH,
                    client_id="client-1",
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=100,
                    currency="USD",
                ),
            ],
        )


def test_custom_transaction_double_entry(db_session):
    service = InternalLedgerService(db_session)
    with pytest.raises(ValueError, match="unbalanced"):
        service.post_transaction(
            tenant_id=1,
            transaction_type=InternalLedgerTransactionType.ACCOUNTING_EXPORT_CONFIRMED,
            external_ref_type="TEST",
            external_ref_id="ref-2",
            idempotency_key="tx:unbalanced",
            posted_at=None,
            meta=None,
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id="client-1",
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=100,
                    currency="RUB",
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_CASH,
                    client_id="client-1",
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=50,
                    currency="RUB",
                ),
            ],
        )
