from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.audit_log import AuditLog
from app.models.account import AccountType, AccountOwnerType
from app.models.ledger_entry import LedgerDirection
from app.models.posting_batch import PostingBatchType
from app.repositories.accounts_repository import AccountsRepository
from app.services.ledger.posting_engine import PostingEngine, PostingInvariantError, PostingLine


engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def accounts_repo(session):
    return AccountsRepository(session)


@pytest.fixture
def posting_engine(session):
    return PostingEngine(session)


def _client_account(repo: AccountsRepository, currency: str = "RUB") -> int:
    return repo.get_or_create_account(
        client_id="client-1",
        owner_type=AccountOwnerType.CLIENT,
        owner_id="client-1",
        currency=currency,
        account_type=AccountType.CLIENT_MAIN,
    ).id


def _partner_account(repo: AccountsRepository, currency: str = "RUB") -> int:
    return repo.get_or_create_account(
        client_id="partner-1",
        owner_type=AccountOwnerType.PARTNER,
        owner_id="partner-1",
        currency=currency,
        account_type=AccountType.TECHNICAL,
    ).id


def test_posting_idempotent(posting_engine: PostingEngine, accounts_repo: AccountsRepository):
    debit = _client_account(accounts_repo)
    credit = _partner_account(accounts_repo)
    lines = [
        PostingLine(account_id=debit, direction=LedgerDirection.DEBIT, amount=Decimal("100.00"), currency="RUB"),
        PostingLine(account_id=credit, direction=LedgerDirection.CREDIT, amount=Decimal("100.00"), currency="RUB"),
    ]

    first = posting_engine.apply_posting(
        operation_id=uuid4(),
        posting_type=PostingBatchType.CAPTURE,
        idempotency_key="op:1:cap",
        lines=lines,
    )
    second = posting_engine.apply_posting(
        operation_id=uuid4(),
        posting_type=PostingBatchType.CAPTURE,
        idempotency_key="op:1:cap",
        lines=lines,
    )

    assert first.posting_id == second.posting_id
    assert len(second.entries) == 2
    balances = posting_engine.balance_service.snapshot_balances([debit, credit])
    assert balances[debit]["current"] == Decimal("-100.00")
    assert balances[credit]["current"] == Decimal("100.00")


def test_double_entry_invariant(posting_engine: PostingEngine, accounts_repo: AccountsRepository):
    debit = _client_account(accounts_repo)
    credit = _partner_account(accounts_repo)
    imbalanced_lines = [
        PostingLine(account_id=debit, direction=LedgerDirection.DEBIT, amount=Decimal("50.00"), currency="RUB"),
        PostingLine(account_id=credit, direction=LedgerDirection.CREDIT, amount=Decimal("40.00"), currency="RUB"),
    ]

    with pytest.raises(PostingInvariantError):
        posting_engine.apply_posting(
            operation_id=uuid4(),
            posting_type=PostingBatchType.CAPTURE,
            idempotency_key="op:imbalance",
            lines=imbalanced_lines,
        )

    audit = (
        posting_engine.db.query(AuditLog)
        .order_by(AuditLog.ts.desc(), AuditLog.id.desc())
        .first()
    )
    assert audit.event_type == "FINANCIAL_INVARIANT_VIOLATION"
    assert audit.after["invariants"][0]["name"] == "ledger.double_entry"


def test_capture_updates_balances(posting_engine: PostingEngine, accounts_repo: AccountsRepository):
    debit = _client_account(accounts_repo)
    credit = _partner_account(accounts_repo)
    lines = [
        PostingLine(account_id=debit, direction=LedgerDirection.DEBIT, amount=Decimal("75.50"), currency="RUB"),
        PostingLine(account_id=credit, direction=LedgerDirection.CREDIT, amount=Decimal("75.50"), currency="RUB"),
    ]

    posting_engine.apply_posting(
        operation_id=uuid4(),
        posting_type=PostingBatchType.CAPTURE,
        idempotency_key="op:capture",
        lines=lines,
    )

    balances = posting_engine.balance_service.snapshot_balances([debit, credit])
    assert balances[debit]["current"] == Decimal("-75.50")
    assert balances[credit]["current"] == Decimal("75.50")


def test_refund_flow(posting_engine: PostingEngine, accounts_repo: AccountsRepository):
    debit = _client_account(accounts_repo)
    credit = _partner_account(accounts_repo)

    capture_lines = [
        PostingLine(account_id=debit, direction=LedgerDirection.DEBIT, amount=Decimal("120.00"), currency="RUB"),
        PostingLine(account_id=credit, direction=LedgerDirection.CREDIT, amount=Decimal("120.00"), currency="RUB"),
    ]
    posting_engine.apply_posting(
        operation_id=uuid4(),
        posting_type=PostingBatchType.CAPTURE,
        idempotency_key="op:refund:capture",
        lines=capture_lines,
    )

    refund_lines = [
        PostingLine(account_id=credit, direction=LedgerDirection.DEBIT, amount=Decimal("50.00"), currency="RUB"),
        PostingLine(account_id=debit, direction=LedgerDirection.CREDIT, amount=Decimal("50.00"), currency="RUB"),
    ]
    posting_engine.apply_posting(
        operation_id=uuid4(),
        posting_type=PostingBatchType.REFUND,
        idempotency_key="op:refund:apply",
        lines=refund_lines,
    )

    balances = posting_engine.balance_service.snapshot_balances([debit, credit])
    assert balances[debit]["current"] == Decimal("-70.00")
    assert balances[credit]["current"] == Decimal("70.00")


def test_currency_mismatch_blocks_posting(posting_engine: PostingEngine, accounts_repo: AccountsRepository):
    debit = _client_account(accounts_repo, currency="RUB")
    credit = _partner_account(accounts_repo, currency="RUB")
    lines = [
        PostingLine(account_id=debit, direction=LedgerDirection.DEBIT, amount=Decimal("10.00"), currency="USD"),
        PostingLine(account_id=credit, direction=LedgerDirection.CREDIT, amount=Decimal("10.00"), currency="USD"),
    ]

    with pytest.raises(PostingInvariantError):
        posting_engine.apply_posting(
            operation_id=uuid4(),
            posting_type=PostingBatchType.CAPTURE,
            idempotency_key="op:fx",
            lines=lines,
        )

    audit = (
        posting_engine.db.query(AuditLog)
        .order_by(AuditLog.ts.desc(), AuditLog.id.desc())
        .first()
    )
    assert audit.event_type == "FINANCIAL_INVARIANT_VIOLATION"
    assert audit.after["invariants"][0]["name"] == "ledger.currency_match"
