import pytest

from app.db import reset_engine
from app.models.operation import Operation, OperationStatus, OperationType
from app.services.commission import compute_posting_result


@pytest.fixture(autouse=True)
def _use_sqlite(monkeypatch: pytest.MonkeyPatch):
    import app.db as db

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(db, "DATABASE_URL", "sqlite:///:memory:", raising=False)
    monkeypatch.setattr(db, "raw_db_url", "sqlite:///:memory:", raising=False)
    reset_engine()


def test_commission_split_default_rate():
    operation = Operation(
        ext_operation_id="ext-op-1",
        operation_type=OperationType.COMMIT,
        status=OperationStatus.COMPLETED,
        merchant_id="m1",
        terminal_id="t1",
        client_id="c1",
        card_id="card-1",
        product_id="prod-1",
        amount=1_000,
        amount_settled=1_000,
        currency="RUB",
        quantity=None,
        unit_price=None,
        captured_amount=1_000,
        refunded_amount=0,
        response_code="00",
        response_message="OK",
        authorized=True,
    )

    result = compute_posting_result(operation, commission_rate=0.01)

    assert result["gross_amount"] == 1_000
    assert result["platform_commission"] == 10
    assert result["base_cost"] == 990
    assert result["commission_rate"] == 0.01
