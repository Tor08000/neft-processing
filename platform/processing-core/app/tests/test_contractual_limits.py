from datetime import datetime, timedelta, timezone

import pytest

from app.models.contract_limits import LimitConfig, LimitConfigScope, LimitType, LimitWindow, TariffPlan
from app.models.fuel import FuelNetwork, FuelStation, FuelStationNetwork
from app.models.operation import Operation, OperationStatus, OperationType
from app.services.limits_service import check_contractual_limits
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture()
def db_session():
    tables = (
        TariffPlan.__table__,
        FuelNetwork.__table__,
        FuelStationNetwork.__table__,
        FuelStation.__table__,
        LimitConfig.__table__,
        Operation.__table__,
    )
    with scoped_session_context(tables=tables) as session:
        yield session


def _add_operation(db, *, client_id: str, card_id: str, amount: int, created_at: datetime):
    op = Operation(
        ext_operation_id=f"op-{created_at.timestamp()}-{amount}",
        created_at=created_at,
        operation_type=OperationType.AUTH,
        status=OperationStatus.POSTED,
        merchant_id="m1",
        terminal_id="t1",
        client_id=client_id,
        card_id=card_id,
        amount=amount,
        currency="RUB",
        authorized=True,
        response_code="00",
        response_message="OK",
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return op


def test_daily_amount_limit_blocks_excess(db_session):
    db_session.add(
        LimitConfig(
            scope=LimitConfigScope.CLIENT,
            subject_ref="client-1",
            limit_type=LimitType.DAILY_AMOUNT,
            value=1_000,
            window=LimitWindow.DAILY,
        )
    )
    db_session.commit()

    now = datetime.now(timezone.utc)
    _add_operation(db_session, client_id="client-1", card_id="card-1", amount=900, created_at=now)

    evaluation = check_contractual_limits(
        db_session,
        client_id="client-1",
        card_id="card-1",
        amount=200,
        quantity=1,
        now=now,
    )
    assert not evaluation.approved
    assert evaluation.violations[0].projected > evaluation.violations[0].limit.value


def test_card_limit_more_strict_than_client(db_session):
    db_session.add_all(
        [
            LimitConfig(
                scope=LimitConfigScope.CLIENT,
                subject_ref="client-1",
                limit_type=LimitType.DAILY_AMOUNT,
                value=2_000,
                window=LimitWindow.DAILY,
            ),
            LimitConfig(
                scope=LimitConfigScope.CARD,
                subject_ref="card-1",
                limit_type=LimitType.DAILY_AMOUNT,
                value=600,
                window=LimitWindow.DAILY,
            ),
        ]
    )
    db_session.commit()

    now = datetime.now(timezone.utc) - timedelta(hours=1)
    _add_operation(db_session, client_id="client-1", card_id="card-1", amount=400, created_at=now)

    evaluation = check_contractual_limits(
        db_session,
        client_id="client-1",
        card_id="card-1",
        amount=300,
        quantity=1,
        now=now,
    )
    assert not evaluation.approved
    assert any(v.limit.scope == LimitConfigScope.CARD for v in evaluation.violations)
