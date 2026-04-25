from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransaction,
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
from ._money_router_harness import RECONCILIATION_SERVICE_TEST_TABLES, money_session_context


@pytest.fixture
def db_session() -> Session:
    with money_session_context(tables=RECONCILIATION_SERVICE_TEST_TABLES) as session:
        yield session


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
    stored = db_session.query(ExternalStatement).filter(ExternalStatement.id == statement.id).one()
    assert stored.audit_event_id is not None
    assert db_session.query(ExternalStatement).filter(ExternalStatement.id == statement.id).count() == 1
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "EXTERNAL_STATEMENT_UPLOADED", AuditLog.entity_id == str(statement.id))
        .count()
        == 1
    )
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


def test_external_reconciliation_creates_total_specific_balance_mismatches(db_session):
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

    discrepancies = (
        db_session.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.run_id == run_id)
        .filter(ReconciliationDiscrepancy.discrepancy_type == ReconciliationDiscrepancyType.BALANCE_MISMATCH)
        .all()
    )
    kinds = {item.details["kind"]: item for item in discrepancies}
    assert set(kinds) == {"total_out", "closing_balance"}
    assert kinds["total_out"].status == ReconciliationDiscrepancyStatus.OPEN
    assert kinds["closing_balance"].status == ReconciliationDiscrepancyStatus.OPEN


def test_resolve_discrepancy_with_adjustment(db_session):
    _post_simple_transaction(db_session, amount=100, currency="RUB", balance_after=100)
    account_id = (
        db_session.query(InternalLedgerEntry.account_id)
        .join(InternalLedgerAccount, InternalLedgerEntry.account_id == InternalLedgerAccount.id)
        .filter(InternalLedgerAccount.account_type == InternalLedgerAccountType.CLIENT_AR)
        .first()[0]
    )

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


def test_resolve_discrepancy_with_adjustment_registers_postings_audit_chain_and_blocks_duplicates(db_session):
    _post_simple_transaction(db_session, amount=100, currency="RUB", balance_after=100)
    account_id = (
        db_session.query(InternalLedgerEntry.account_id)
        .join(InternalLedgerAccount, InternalLedgerEntry.account_id == InternalLedgerAccount.id)
        .filter(InternalLedgerAccount.account_type == InternalLedgerAccountType.CLIENT_AR)
        .first()[0]
    )

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

    tx_id = resolve_discrepancy_with_adjustment(db_session, str(discrepancy.id), note="regression")
    db_session.commit()

    tx = (
        db_session.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.id == tx_id)
        .one()
    )
    assert tx.transaction_type == InternalLedgerTransactionType.ADJUSTMENT
    assert tx.external_ref_type == "RECONCILIATION_DISCREPANCY"
    assert tx.external_ref_id == str(discrepancy.id)

    postings = (
        db_session.query(InternalLedgerEntry, InternalLedgerAccount)
        .join(InternalLedgerAccount, InternalLedgerEntry.account_id == InternalLedgerAccount.id)
        .filter(InternalLedgerEntry.ledger_transaction_id == tx.id)
        .order_by(InternalLedgerEntry.direction.asc(), InternalLedgerAccount.account_type.asc())
        .all()
    )
    assert len(postings) == 2
    debit_entry, debit_account = next(
        (entry, account)
        for entry, account in postings
        if entry.direction == InternalLedgerEntryDirection.DEBIT
    )
    credit_entry, credit_account = next(
        (entry, account)
        for entry, account in postings
        if entry.direction == InternalLedgerEntryDirection.CREDIT
    )
    assert debit_account.id == account_id
    assert debit_account.account_type == InternalLedgerAccountType.CLIENT_AR
    assert debit_entry.amount == 50
    assert credit_account.account_type == InternalLedgerAccountType.SUSPENSE
    assert credit_entry.amount == 50

    ledger_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "ledger_transaction", AuditLog.entity_id == str(tx.id))
        .one()
    )
    prior_ledger_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "ledger_transaction", AuditLog.tenant_id == 1)
        .filter(AuditLog.entity_id != str(tx.id))
        .one()
    )
    resolve_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "DISCREPANCY_RESOLVED", AuditLog.entity_id == str(discrepancy.id))
        .one()
    )
    assert ledger_audit.after["external_ref_type"] == "RECONCILIATION_DISCREPANCY"
    assert ledger_audit.after["external_ref_id"] == str(discrepancy.id)
    assert ledger_audit.tenant_id == 1
    assert ledger_audit.prev_hash == prior_ledger_audit.hash
    assert resolve_audit.after["adjustment_tx_id"] == str(tx.id)
    assert resolve_audit.tenant_id is None
    assert resolve_audit.prev_hash == "GENESIS"
    assert ledger_audit.hash
    assert resolve_audit.hash

    with pytest.raises(ValueError, match="discrepancy_not_open"):
        resolve_discrepancy_with_adjustment(db_session, str(discrepancy.id), note="rerun")

    assert (
        db_session.query(InternalLedgerTransaction)
        .filter(InternalLedgerTransaction.external_ref_type == "RECONCILIATION_DISCREPANCY")
        .filter(InternalLedgerTransaction.external_ref_id == str(discrepancy.id))
        .count()
        == 1
    )
    assert (
        db_session.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.ledger_transaction_id == tx.id)
        .count()
        == 2
    )
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.event_type == "DISCREPANCY_RESOLVED", AuditLog.entity_id == str(discrepancy.id))
        .count()
        == 1
    )
