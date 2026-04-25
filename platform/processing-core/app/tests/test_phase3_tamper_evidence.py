from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db import Base
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
    InternalLedgerTransactionType,
)
from app.models.billing_period import BillingPeriod, BillingPeriodStatus
from app.models.invoice import InvoiceStatus
from app.models.settlement_v1 import SettlementPeriod, SettlementPeriodStatus
from app.repositories.billing_repository import BillingInvoiceData, BillingLineData, BillingRepository
from app.services.finance import FinanceService, PaymentIdempotencyConflict
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService, verify_ledger_chain
from app.services.settlement_service import verify_period_hash


ADMIN_FINANCE_TOKEN = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "phase3-finance-tester"}


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


def _is_postgres(session) -> bool:
    return bool(session.bind and session.bind.dialect.name == "postgresql")


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
    period = db_session.get(BillingPeriod, invoice.billing_period_id)
    assert period is not None
    period.status = BillingPeriodStatus.FINALIZED
    period.finalized_at = datetime.now(timezone.utc)
    db_session.flush()
    service = FinanceService(db_session)
    service.apply_payment(
        invoice_id=invoice.id,
        amount=200,
        currency="RUB",
        idempotency_key="phase3-payment-1",
        request_ctx=None,
        token=ADMIN_FINANCE_TOKEN,
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


def test_ledger_transaction_raw_sql_tamper_blocked(db_session):
    _seed_ledger_tx(db_session)
    baseline_ok, _baseline_err = verify_ledger_chain(db_session)
    db_session.commit()

    tx = db_session.query(InternalLedgerTransaction).order_by(InternalLedgerTransaction.batch_sequence.desc()).first()
    with pytest.raises(Exception):
        db_session.execute(
            text("UPDATE internal_ledger_transactions SET batch_hash = :h WHERE id = :id"),
            {"id": str(tx.id), "h": "0" * 64},
        )
        db_session.flush()
    db_session.rollback()

    ok_after, err_after = verify_ledger_chain(db_session)
    if baseline_ok:
        assert ok_after is True
        assert err_after is None


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
        {"k": "phase3-payment-1"},
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
            token=ADMIN_FINANCE_TOKEN,
        )


@pytest.mark.phase3
def test_phase3_pg_triggers_exist_for_immutability(db_session):
    if not _is_postgres(db_session):
        pytest.skip("Postgres-only: trigger catalog checks")

    rows = db_session.execute(
        text(
            """
            SELECT tg.tgname AS name
            FROM pg_trigger tg
            JOIN pg_class c ON c.oid = tg.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE NOT tg.tgisinternal
              AND c.relname = 'internal_ledger_entries'
            """
        )
    ).fetchall()
    trigger_names = {r[0] for r in rows}

    assert "ledger_no_update" in trigger_names, f"Expected ledger_no_update trigger, found: {sorted(trigger_names)}"
    assert "ledger_no_delete" in trigger_names, f"Expected ledger_no_delete trigger, found: {sorted(trigger_names)}"


@pytest.mark.phase3
def test_phase3_db_rejects_unbalanced_batch_via_sql(db_session):
    if not _is_postgres(db_session):
        pytest.skip("Postgres-only: DB-level constraint/trigger enforcement proof")

    try:
        db_session.execute(
            text(
                """
                INSERT INTO internal_ledger_transactions (
                    id,
                    tenant_id,
                    transaction_type,
                    external_ref_type,
                    external_ref_id,
                    idempotency_key,
                    total_amount,
                    total_debit,
                    total_credit,
                    currency,
                    batch_sequence,
                    previous_batch_hash,
                    batch_hash,
                    posted_at,
                    meta
                ) VALUES (
                    :id,
                    1,
                    'ADJUSTMENT',
                    'TEST',
                    'bad-sql-batch',
                    :idempotency_key,
                    100,
                    100,
                    99,
                    'RUB',
                    10_001,
                    'GENESIS_INTERNAL_LEDGER_V1',
                    :batch_hash,
                    NOW(),
                    '{}'::jsonb
                )
                """
            ),
            {
                "id": str(uuid4()),
                "idempotency_key": f"phase3-unbalanced-sql-{uuid4()}",
                "batch_hash": "f" * 64,
            },
        )
        db_session.commit()
        pytest.fail("Expected DB to reject unbalanced ledger batch totals, but commit succeeded")
    except (IntegrityError, DBAPIError):
        db_session.rollback()
