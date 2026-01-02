from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.db import Base, SessionLocal, engine
from app.models.audit_log import AuditLog
from app.models.internal_ledger import (
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.models.reconciliation import (
    ExternalStatement,
    ReconciliationDiscrepancy,
    ReconciliationDiscrepancyStatus,
    ReconciliationDiscrepancyType,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
)
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService
from app.services.reconciliation_service import (
    resolve_discrepancy_with_adjustment,
    run_external_reconciliation,
    run_internal_reconciliation,
    upload_external_statement,
)


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


def _post_simple_transaction(db_session, *, amount: int, currency: str, balance_after: int | None = None) -> None:
    service = InternalLedgerService(db_session)
    meta = {"balance_after": balance_after} if balance_after is not None else None
    service.post_transaction(
        tenant_id=1,
        transaction_type=InternalLedgerTransactionType.ACCOUNTING_EXPORT_CONFIRMED,
        external_ref_type="TEST",
        external_ref_id="ref-1",
        idempotency_key=f"tx:{amount}:{balance_after}",
        posted_at=None,
        meta=None,
        entries=[
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.CLIENT_AR,
                client_id="client-1",
                direction=InternalLedgerEntryDirection.DEBIT,
                amount=amount,
                currency=currency,
                meta=meta,
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.SUSPENSE,
                client_id=None,
                direction=InternalLedgerEntryDirection.CREDIT,
                amount=amount,
                currency=currency,
            ),
        ],
    )


def test_internal_reconciliation_no_mismatches(db_session):
    _post_simple_transaction(db_session, amount=100, currency="RUB", balance_after=100)
    period_start = datetime.now(timezone.utc) - timedelta(days=1)
    period_end = datetime.now(timezone.utc) + timedelta(days=1)

    run_id = run_internal_reconciliation(db_session, period_start=period_start, period_end=period_end)
    db_session.commit()

    run = db_session.query(ReconciliationRun).filter(ReconciliationRun.id == run_id).one()
    assert run.status == ReconciliationRunStatus.COMPLETED
    assert run.summary["mismatches_found"] == 0
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "RECONCILIATION_RUN_COMPLETED", AuditLog.entity_id == run_id)
        .count()
        == 1
    )


def test_internal_reconciliation_creates_mismatch(db_session):
    _post_simple_transaction(db_session, amount=100, currency="RUB", balance_after=200)
    period_start = datetime.now(timezone.utc) - timedelta(days=1)
    period_end = datetime.now(timezone.utc) + timedelta(days=1)

    run_id = run_internal_reconciliation(db_session, period_start=period_start, period_end=period_end)
    db_session.commit()

    discrepancy = (
        db_session.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.run_id == run_id)
        .one()
    )
    assert discrepancy.discrepancy_type == ReconciliationDiscrepancyType.BALANCE_MISMATCH
    assert discrepancy.status == ReconciliationDiscrepancyStatus.OPEN


def test_external_statement_upload_is_worm(db_session):
    period_start = datetime.now(timezone.utc) - timedelta(days=10)
    period_end = datetime.now(timezone.utc)
    statement = upload_external_statement(
        db_session,
        provider="bank-x",
        period_start=period_start,
        period_end=period_end,
        currency="RUB",
        total_in=Decimal("1000"),
        total_out=Decimal("200"),
        closing_balance=Decimal("800"),
        lines=[{"id": "line-1", "amount": "100"}],
    )
    db_session.commit()
    assert db_session.query(ExternalStatement).filter(ExternalStatement.id == statement.id).count() == 1
    with pytest.raises(ValueError, match="statement_already_uploaded"):
        upload_external_statement(
            db_session,
            provider="bank-x",
            period_start=period_start,
            period_end=period_end,
            currency="RUB",
            total_in=Decimal("1000"),
            total_out=Decimal("200"),
            closing_balance=Decimal("800"),
            lines=[{"id": "line-1", "amount": "100"}],
        )


def test_external_reconciliation_closing_balance_mismatch(db_session):
    _post_simple_transaction(db_session, amount=500, currency="RUB", balance_after=500)
    period_start = datetime.now(timezone.utc) - timedelta(days=1)
    period_end = datetime.now(timezone.utc) + timedelta(days=1)
    statement = upload_external_statement(
        db_session,
        provider="bank-x",
        period_start=period_start,
        period_end=period_end,
        currency="RUB",
        total_in=Decimal("500"),
        total_out=Decimal("0"),
        closing_balance=Decimal("450"),
        lines=[{"id": "line-1", "amount": "500"}],
    )

    run_id = run_external_reconciliation(db_session, statement_id=str(statement.id))
    db_session.commit()

    discrepancy = (
        db_session.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.run_id == run_id)
        .filter(ReconciliationDiscrepancy.discrepancy_type == ReconciliationDiscrepancyType.BALANCE_MISMATCH)
        .one()
    )
    assert discrepancy.status == ReconciliationDiscrepancyStatus.OPEN


def test_resolve_discrepancy_with_adjustment(db_session):
    _post_simple_transaction(db_session, amount=100, currency="RUB", balance_after=100)
    account_id = db_session.query(InternalLedgerEntry.account_id).first()[0]

    run = ReconciliationRun(
        scope=ReconciliationScope.INTERNAL,
        period_start=datetime.now(timezone.utc) - timedelta(days=1),
        period_end=datetime.now(timezone.utc) + timedelta(days=1),
        status=ReconciliationRunStatus.COMPLETED,
    )
    db_session.add(run)
    db_session.flush()

    discrepancy = ReconciliationDiscrepancy(
        run_id=run.id,
        ledger_account_id=account_id,
        currency="RUB",
        discrepancy_type=ReconciliationDiscrepancyType.BALANCE_MISMATCH,
        internal_amount=Decimal("100"),
        external_amount=Decimal("150"),
        delta=Decimal("50"),
        status=ReconciliationDiscrepancyStatus.OPEN,
    )
    db_session.add(discrepancy)
    db_session.commit()

    tx_id = resolve_discrepancy_with_adjustment(db_session, str(discrepancy.id), note="test")
    db_session.commit()

    updated = db_session.query(ReconciliationDiscrepancy).filter(ReconciliationDiscrepancy.id == discrepancy.id).one()
    assert updated.status == ReconciliationDiscrepancyStatus.RESOLVED
    assert updated.resolution["adjustment_tx_id"] == tx_id
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "DISCREPANCY_RESOLVED", AuditLog.entity_id == str(discrepancy.id))
        .count()
        == 1
    )
