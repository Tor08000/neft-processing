from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.db import Base, SessionLocal, engine
from app.models.client import Client
from app.models.invoice import InvoiceStatus
from app.models.operation import Operation, OperationStatus, OperationType
from app.services.billing_metrics import metrics
from app.services.billing_service import generate_invoices_for_period
from app.repositories.billing_repository import BillingRepository


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    metrics.reset()
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_operation(session, client_id: str, *, occurred_at: datetime) -> None:
    session.add(
        Operation(
            operation_id="op-1",
            operation_type=OperationType.AUTH,
            status=OperationStatus.COMPLETED,
            merchant_id="m1",
            terminal_id="t1",
            client_id=client_id,
            card_id="card-1",
            product_id="diesel",
            amount=1000,
            currency="RUB",
            created_at=occurred_at,
        )
    )
    session.commit()


def test_metrics_record_successful_generation(monkeypatch: pytest.MonkeyPatch):
    client_uuid = uuid4()
    client_id = str(client_uuid)
    session = SessionLocal()
    session.add(Client(id=client_uuid, name="Client", tariff_plan="BASIC", status="ACTIVE"))
    session.commit()

    _seed_operation(session, client_id, occurred_at=datetime(2024, 1, 15, tzinfo=timezone.utc))

    invoices = generate_invoices_for_period(
        session, period_from=date(2024, 1, 1), period_to=date(2024, 1, 31), status=InvoiceStatus.ISSUED
    )

    assert len(invoices) == 1
    assert metrics.last_run_generated == 1
    assert metrics.generated_invoices_total >= 1
    period_key = "2024-01-01:2024-01-31"
    assert metrics.billed_amounts.get(period_key) == invoices[0].total_with_tax


def test_metrics_count_errors(monkeypatch: pytest.MonkeyPatch):
    client_uuid = uuid4()
    client_id = str(client_uuid)
    session = SessionLocal()
    session.add(Client(id=client_uuid, name="Client", tariff_plan="BASIC", status="ACTIVE"))
    session.commit()

    _seed_operation(session, client_id, occurred_at=datetime(2024, 2, 10, tzinfo=timezone.utc))

    def _boom(self, data, *, auto_commit=True):  # noqa: ANN001, ANN002
        raise RuntimeError("boom")

    monkeypatch.setattr(BillingRepository, "create_invoice", _boom)

    generated = generate_invoices_for_period(
        session, period_from=date(2024, 2, 1), period_to=date(2024, 2, 28), status=InvoiceStatus.ISSUED
    )

    assert generated == []
    assert metrics.billing_errors == 1
