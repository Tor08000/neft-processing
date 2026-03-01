from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db import Base
from app.domains.ledger.enums import EntryType, LineDirection
from app.domains.ledger.errors import IdempotencyMismatch, InvariantViolation
from app.domains.ledger.invariants import LedgerInvariants
from app.domains.ledger.models import LedgerAccountBalanceV1, LedgerAccountV1, LedgerEntryV1, LedgerLineV1
from app.domains.ledger.schemas import LedgerLineIn, LedgerPostRequest
from app.domains.ledger.service import InternalLedgerService


def _line(direction: LineDirection, amount: str = "100", currency: str = "RUB"):
    return {"direction": direction.value, "amount": amount, "currency": currency}


@pytest.fixture(autouse=True)
def _setup_v1_tables(test_db_engine):
    if test_db_engine.dialect.name != "sqlite":
        yield
        return
    tables = [LedgerLineV1.__table__, LedgerEntryV1.__table__, LedgerAccountBalanceV1.__table__, LedgerAccountV1.__table__]
    Base.metadata.drop_all(bind=test_db_engine, tables=tables)
    Base.metadata.create_all(bind=test_db_engine, tables=tables)
    yield


@pytest.fixture
def db_session(test_db_session):
    return test_db_session


def _valid_request(idempotency_key: str = "idem-1") -> LedgerPostRequest:
    return LedgerPostRequest(
        entry_type=EntryType.CAPTURE,
        idempotency_key=idempotency_key,
        correlation_id="corr-1",
        dimensions={"client_id": "c1", "partner_id": "p1", "operation_id": "op1"},
        lines=[
            LedgerLineIn(account_code="CLIENT_AR", owner_id=uuid4(), direction=LineDirection.DEBIT, amount=Decimal("100.00"), currency="RUB"),
            LedgerLineIn(account_code="PARTNER_AP", owner_id=uuid4(), direction=LineDirection.CREDIT, amount=Decimal("100.00"), currency="RUB"),
        ],
    )


def test_invariant_rejects_unbalanced_lines():
    with pytest.raises(InvariantViolation, match="ledger.unbalanced"):
        LedgerInvariants.assert_balanced([_line(LineDirection.DEBIT, "100"), _line(LineDirection.CREDIT, "90")])


def test_invariant_rejects_zero_amount():
    with pytest.raises(InvariantViolation, match="ledger.amount_positive"):
        LedgerInvariants.assert_positive([_line(LineDirection.DEBIT, "0")])


def test_invariant_rejects_negative_amount():
    with pytest.raises(InvariantViolation, match="ledger.amount_positive"):
        LedgerInvariants.assert_positive([_line(LineDirection.DEBIT, "-1")])


def test_invariant_rejects_mixed_currency():
    with pytest.raises(InvariantViolation, match="ledger.single_currency"):
        LedgerInvariants.assert_single_currency([_line(LineDirection.DEBIT, "10", "RUB"), _line(LineDirection.CREDIT, "10", "USD")])


def test_invariant_rejects_missing_required_dimensions():
    with pytest.raises(InvariantViolation, match="ledger.required_dimension"):
        LedgerInvariants.assert_required_dimensions(EntryType.CAPTURE, {"client_id": "c1"})


def test_invariant_rejects_idempotency_payload_mismatch():
    with pytest.raises(IdempotencyMismatch):
        LedgerInvariants.assert_idempotency_match({"a": 1}, {"a": 2})


def test_service_posts_balanced_entry(db_session):
    out = InternalLedgerService(db_session).post_entry(_valid_request("idem-service-1"))
    assert out.status == "POSTED"
    assert len(out.lines) == 2


def test_service_rejects_unbalanced_lines(db_session):
    req = _valid_request("idem-service-2")
    req.lines[1].amount = Decimal("99.00")
    with pytest.raises(InvariantViolation, match="ledger.unbalanced"):
        InternalLedgerService(db_session).post_entry(req)


def test_service_rejects_zero_amount(db_session):
    req = _valid_request("idem-service-3")
    req.lines[0].amount = Decimal("0")
    with pytest.raises(InvariantViolation, match="ledger.amount_positive"):
        InternalLedgerService(db_session).post_entry(req)


def test_service_rejects_negative_amount(db_session):
    req = _valid_request("idem-service-4")
    req.lines[0].amount = Decimal("-10")
    with pytest.raises(InvariantViolation, match="ledger.amount_positive"):
        InternalLedgerService(db_session).post_entry(req)


def test_service_rejects_mixed_currency(db_session):
    req = _valid_request("idem-service-5")
    req.lines[1].currency = "USD"
    with pytest.raises(InvariantViolation, match="ledger.single_currency"):
        InternalLedgerService(db_session).post_entry(req)


def test_service_rejects_missing_dimensions(db_session):
    req = _valid_request("idem-service-6")
    req.dimensions = {"client_id": "c1"}
    with pytest.raises(InvariantViolation, match="ledger.required_dimension"):
        InternalLedgerService(db_session).post_entry(req)


def test_idempotency_replay_returns_existing(db_session):
    service = InternalLedgerService(db_session)
    first = service.post_entry(_valid_request("idem-replay"))
    second = service.post_entry(_valid_request("idem-replay"))
    assert first.entry_id == second.entry_id


def test_idempotency_mismatch_rejected(db_session):
    service = InternalLedgerService(db_session)
    service.post_entry(_valid_request("idem-mismatch"))
    changed = _valid_request("idem-mismatch")
    changed.lines[1].amount = Decimal("10")
    with pytest.raises(IdempotencyMismatch):
        service.post_entry(changed)


def test_balance_endpoint_like_method_returns_data(db_session):
    service = InternalLedgerService(db_session)
    req = _valid_request("idem-balance")
    owner = str(req.lines[0].owner_id)
    service.post_entry(req)
    balance = service.get_balance(account_code="CLIENT_AR", owner_id=owner, currency="RUB")
    assert Decimal(str(balance["balance"])) == Decimal("100.00")


def test_db_immutability_update_posted_entry_postgres(db_session):
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("Postgres-only")
    service = InternalLedgerService(db_session)
    entry = service.post_entry(_valid_request("idem-pg-immut-1"))
    with pytest.raises(Exception):
        db_session.execute(text("UPDATE internal_ledger_v1_entries SET narrative='x' WHERE id=:id"), {"id": str(entry.entry_id)})


def test_db_immutability_delete_line_postgres(db_session):
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("Postgres-only")
    service = InternalLedgerService(db_session)
    entry = service.post_entry(_valid_request("idem-pg-immut-2"))
    line_id = db_session.execute(text("SELECT id FROM internal_ledger_v1_lines WHERE entry_id=:id LIMIT 1"), {"id": str(entry.entry_id)}).scalar_one()
    with pytest.raises(Exception):
        db_session.execute(text("DELETE FROM internal_ledger_v1_lines WHERE id=:id"), {"id": str(line_id)})


def test_db_balance_constraint_trigger_postgres(db_session):
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("Postgres-only")
    entry_id = uuid4()
    account_id = uuid4()
    db_session.execute(
        text("INSERT INTO internal_ledger_v1_accounts (id, account_code, account_type, owner_type, currency, status) VALUES (:id, :c, 'ASSET', 'PLATFORM', 'RUB', 'ACTIVE')"),
        {"id": str(account_id), "c": f"CLEARING-{uuid4()}"},
    )
    db_session.execute(
        text("INSERT INTO internal_ledger_v1_entries (id, status, entry_type, idempotency_key, correlation_id, dimensions) VALUES (:id, 'POSTED', 'ADJUSTMENT', :k, :corr, '{}'::jsonb)"),
        {"id": str(entry_id), "k": f"k-{uuid4()}", "corr": f"corr-{uuid4()}"},
    )
    db_session.execute(
        text("INSERT INTO internal_ledger_v1_lines (id, entry_id, line_no, account_id, direction, amount, currency) VALUES (:id, :e, 1, :a, 'DEBIT', 100, 'RUB')"),
        {"id": str(uuid4()), "e": str(entry_id), "a": str(account_id)},
    )
    with pytest.raises(Exception):
        db_session.commit()
