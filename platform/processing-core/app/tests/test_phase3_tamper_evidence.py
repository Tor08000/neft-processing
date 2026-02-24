from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import Base
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
    InternalLedgerTransactionType,
)
from app.models.invoice import InvoiceStatus
from app.models.settlement_v1 import SettlementPeriod, SettlementPeriodStatus
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.services.finance import FinanceService, PaymentIdempotencyConflict
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService, verify_ledger_chain
from app.services.settlement_service import verify_period_hash


@pytest.fixture(autouse=True)
def _reset_phase3_tables(test_db_engine):
    if test_db_engine.dialect.name != "sqlite":
        yield
        return
    tables = [
        InternalLedgerEntry.__table__,
        InternalLedgerTransaction.__table__,
        InternalLedgerAccount.__table__,
    ]
    Base.metadata.drop_all(bind=test_db_engine, tables=tables)
    Base.metadata.create_all(bind=test_db_engine, tables=tables)
    yield


@pytest.fixture
def db_session(test_db_session):
    return test_db_session


@pytest.fixture(autouse=True)
def _disable_ledger_audit(monkeypatch, test_db_engine):
    if test_db_engine.dialect.name == "sqlite":
        monkeypatch.setattr(InternalLedgerService, "_emit_audit_event", lambda *args, **kwargs: None)


def _seed_ledger_tx(db_session):
    service = InternalLedgerService(db_session)
    result = service.post_transaction(
        tenant_id=1,
        transaction_type=InternalLedgerTransactionType.ACCOUNTING_EXPORT_CONFIRMED,
        external_ref_type="TEST",
        external_ref_id="seed-1",
        idempotency_key="phase3-ledger-seed",
        posted_at=datetime.now(timezone.utc),
        meta={"request_id": "req-1", "actor": "system"},
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.CLIENT_AR,
                client_id="client-1",
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=200,
                currency="RUB",
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.CLIENT_CASH,
                client_id="client-1",
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=200,
                currency="RUB",
            ),
        ],
    )
    db_session.flush()
    return result


def _seed_payment(db_session):
    repo = BillingRepository(db_session)
    invoice = repo.create_invoice(
        BillingInvoiceData(
            client_id="phase3-client",
            period_from=datetime(2024, 1, 1).date(),
            period_to=datetime(2024, 1, 31).date(),
            currency="RUB",
            lines=[BillingLineData(product_id="fuel", liters=None, unit_price=None, line_amount=1000, tax_amount=0)],
        )
    )
    invoice.status = InvoiceStatus.SENT
    db_session.flush()
    service = FinanceService(db_session)
    service.apply_payment(
        invoice_id=invoice.id,
        amount=200,
        currency="RUB",
        idempotency_key="phase3-payment-1",
        request_ctx=None,
        token=None,
    )
    db_session.flush()
    return invoice


def test_ledger_raw_sql_update_delete_blocked(db_session):
    _seed_ledger_tx(db_session)
    entry_id = db_session.query(InternalLedgerEntry.id).first()[0]

    with pytest.raises(Exception):
        db_session.execute(text("UPDATE internal_ledger_entries SET amount = amount + 1 WHERE id = :id"), {"id": str(entry_id)})

    with pytest.raises(Exception):
        db_session.execute(text("DELETE FROM internal_ledger_entries WHERE id = :id"), {"id": str(entry_id)})


def test_ledger_chain_verification_fails_on_tamper(db_session):
    _seed_ledger_tx(db_session)
    baseline_ok, _baseline_err = verify_ledger_chain(db_session)

    tx = db_session.query(InternalLedgerTransaction).order_by(InternalLedgerTransaction.batch_sequence.desc()).first()
    db_session.execute(
        text("UPDATE internal_ledger_transactions SET batch_hash = :h WHERE id = :id"),
        {"id": str(tx.id), "h": "0" * 64},
    )
    db_session.flush()

    ok_after, err_after = verify_ledger_chain(db_session)
    assert ok_after is False
    if baseline_ok:
        assert "batch_hash_mismatch" in str(err_after)


def test_snapshot_tamper_detected():
    period = SettlementPeriod(
        partner_id="partner-1",
        currency="RUB",
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
        status=SettlementPeriodStatus.APPROVED,
        snapshot_payload={"balances": [{"account_id": "a1", "balance_minor": 100}], "last_batch_hash": "abc"},
        period_hash="bogus",
    )
    assert verify_period_hash(period) is False


def test_double_entry_constraint_rejects_unbalanced_batch(db_session):
    tx = InternalLedgerTransaction(
        tenant_id=1,
        transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
        external_ref_type="TEST",
        external_ref_id="bad",
        idempotency_key="phase3-unbalanced-db",
        total_debit=100,
        total_credit=99,
        currency="RUB",
        batch_sequence=999,
        previous_batch_hash="GENESIS_INTERNAL_LEDGER_V1",
        batch_hash="x" * 64,
    )
    db_session.add(tx)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_idempotency_replay_response_hash_mutation_detected(db_session, test_db_engine):
    if test_db_engine.dialect.name != "postgresql":
        pytest.skip("Idempotency response-hash tamper verification is Postgres-only")

    invoice = _seed_payment(db_session)
    payment = db_session.execute(
        text("SELECT id FROM invoice_payments WHERE idempotency_key = :k"),
        {"k": "hash:phase3-payment-1"},
    ).first()
    assert payment is not None

    tamper_blocked = False
    try:
        db_session.execute(
            text("UPDATE invoice_payments SET response_hash = :h WHERE id = :id"),
            {"id": str(payment.id), "h": "f" * 64},
        )
        db_session.flush()
    except Exception:
        tamper_blocked = True
        db_session.rollback()

    if tamper_blocked:
        return

    service = FinanceService(db_session)
    with pytest.raises(PaymentIdempotencyConflict, match="response_hash_mismatch"):
        service.apply_payment(
            invoice_id=invoice.id,
            amount=200,
            currency="RUB",
            idempotency_key="phase3-payment-1",
            request_ctx=None,
            token=None,
        )
