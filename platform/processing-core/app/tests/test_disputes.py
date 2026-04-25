from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.operation import Operation, OperationStatus, OperationType
from app.services.ledger.balance_service import BalanceService
from app.services.operations_scenarios.disputes import (
    PLATFORM_OWNER_ID,
    DisputeService,
    DisputeStateError,
)
from app.models.account import AccountOwnerType, AccountType

from ._money_router_harness import OPERATIONAL_DISPUTE_REFUND_TEST_TABLES, money_session_context

MERCHANT_ID = "11111111-1111-1111-1111-111111111111"
CLIENT_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def session():
    with money_session_context(tables=OPERATIONAL_DISPUTE_REFUND_TEST_TABLES) as db:
        yield db


def _make_operation(db, *, amount: int = 100) -> Operation:
    op = Operation(
        operation_id=str(uuid4()),
        operation_type=OperationType.CAPTURE,
        status=OperationStatus.CAPTURED,
        merchant_id=MERCHANT_ID,
        terminal_id="term-1",
        client_id=CLIENT_ID,
        card_id="card-1",
        amount=amount,
        currency="RUB",
        captured_amount=amount,
        refunded_amount=0,
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return op


def test_dispute_hold_place_and_release(session):
    op = _make_operation(session, amount=150)
    service = DisputeService(session)
    opened = service.open_dispute(
        operation=op,
        amount=80,
        initiator="tester",
        idempotency_key="disp-hold",
        place_hold=True,
    )
    dispute = opened.dispute
    assert dispute.hold_posting_id is not None
    assert dispute.hold_placed is True

    result = service.reject(dispute=dispute, actor="tester", idempotency_key="disp-hold")
    updated = result.dispute
    assert updated.status.name == "REJECTED"
    assert updated.hold_placed is False

    payable = service._partner_payable(op)
    reserve = service._dispute_reserve(op.currency)
    balances = BalanceService(session).snapshot_balances([payable, reserve])
    assert balances[reserve]["hold"] == Decimal("0")
    assert balances[payable]["hold"] == Decimal("0")


def test_dispute_accept_posts_refund_and_fee(session):
    op = _make_operation(session, amount=200)
    service = DisputeService(session)
    opened = service.open_dispute(
        operation=op,
        amount=100,
        initiator="tester",
        idempotency_key="disp-accept",
        fee_amount=10,
        place_hold=True,
    )
    dispute = opened.dispute
    accepted = service.accept(
        dispute=dispute,
        operation=op,
        initiator="tester",
        idempotency_key="disp-accept",
    )
    updated = accepted.dispute
    assert updated.status.name == "ACCEPTED"
    assert updated.resolution_posting_id is not None

    client_account = service._client_main(op)
    reserve = service._dispute_reserve(op.currency)
    revenue_account = service.accounts_repo.get_or_create_account(
        client_id=PLATFORM_OWNER_ID,
        owner_type=AccountOwnerType.PLATFORM,
        owner_id=PLATFORM_OWNER_ID,
        currency=op.currency,
        account_type=AccountType.TECHNICAL,
        tariff_id="DISPUTE_FEE_REVENUE",
    ).id
    balances = BalanceService(session).snapshot_balances([client_account, reserve, revenue_account])
    assert balances[client_account]["current"] == Decimal("100")
    assert balances[reserve]["current"] == Decimal("-110")
    assert balances[revenue_account]["current"] == Decimal("10")


def test_dispute_state_machine_forbidden_transitions(session):
    op = _make_operation(session)
    service = DisputeService(session)
    opened = service.open_dispute(
        operation=op,
        amount=50,
        initiator="tester",
        idempotency_key="disp-state",
    )
    dispute = opened.dispute

    with pytest.raises(DisputeStateError):
        service.close(dispute, actor="tester")
