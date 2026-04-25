from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.clearing import Clearing

from ._money_router_harness import (
    ADMIN_CLEARING_TEST_TABLES,
    admin_clearing_client_context,
    money_session_context,
)


@pytest.fixture
def session() -> Session:
    with money_session_context(tables=ADMIN_CLEARING_TEST_TABLES) as db:
        yield db


@pytest.fixture
def admin_client(session: Session) -> TestClient:
    with admin_clearing_client_context(db_session=session) as api_client:
        yield api_client


def _create_period(session: Session, target_date: date) -> BillingPeriod:
    period = BillingPeriod(
        period_type=BillingPeriodType.DAILY,
        start_at=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=BillingPeriodStatus.OPEN,
    )
    session.add(period)
    session.flush()
    return period


def test_admin_clearing_no_data_returns_empty_batch_list(admin_client: TestClient, session: Session):
    target_date = date(2024, 1, 1)

    response = admin_client.post("/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()})

    assert response.status_code == 200
    body = response.json()
    assert body == {"clearing_date": target_date.isoformat(), "created": 0, "reason": "no_data"}

    job_runs = session.query(BillingJobRun).filter(BillingJobRun.job_type == BillingJobType.CLEARING).all()
    assert len(job_runs) == 1
    assert job_runs[0].status == BillingJobStatus.SUCCESS
    assert job_runs[0].metrics == {"created": 0, "reason": "no_data"}


def test_admin_clearing_reuses_successful_run_result(admin_client: TestClient, session: Session):
    target_date = date(2024, 1, 2)
    period = _create_period(session, target_date)
    session.add_all(
        [
            BillingSummary(
                billing_date=target_date,
                billing_period_id=period.id,
                merchant_id="m-one",
                client_id="c1",
                currency="RUB",
                total_amount=500,
                operations_count=2,
                commission_amount=0,
                status=BillingSummaryStatus.FINALIZED,
            ),
            BillingSummary(
                billing_date=target_date,
                billing_period_id=period.id,
                merchant_id="m-one",
                client_id="c2",
                currency="RUB",
                total_amount=700,
                operations_count=1,
                commission_amount=0,
                status=BillingSummaryStatus.FINALIZED,
            ),
        ]
    )
    session.commit()

    first_response = admin_client.post("/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()})
    assert first_response.status_code == 200
    first_body = first_response.json()
    assert first_body == {"clearing_date": target_date.isoformat(), "created": 1}

    second_response = admin_client.post("/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()})
    assert second_response.status_code == 200
    second_body = second_response.json()
    assert second_body == {"clearing_date": target_date.isoformat(), "created": 0, "reason": "already_exists"}

    stored_batches = session.query(Clearing).filter(Clearing.batch_date == target_date).all()
    assert len(stored_batches) == 1

    job_runs = (
        session.query(BillingJobRun)
        .filter(BillingJobRun.job_type == BillingJobType.CLEARING)
        .order_by(BillingJobRun.started_at.asc())
        .all()
    )
    assert len(job_runs) == 2
    assert all(job.status == BillingJobStatus.SUCCESS for job in job_runs)
    assert job_runs[0].metrics == {"created": 1}
    assert job_runs[1].metrics == {"created": 0, "reason": "already_exists"}


def test_admin_clearing_creates_from_summaries(admin_client: TestClient, session: Session):
    target_date = date(2024, 1, 3)
    period = _create_period(session, target_date)
    session.add_all(
        [
            BillingSummary(
                billing_date=target_date,
                billing_period_id=period.id,
                merchant_id="m-one",
                client_id="c1",
                currency="RUB",
                total_amount=500,
                operations_count=2,
                commission_amount=0,
                status=BillingSummaryStatus.FINALIZED,
            ),
            BillingSummary(
                billing_date=target_date,
                billing_period_id=period.id,
                merchant_id="m-two",
                client_id="c2",
                currency="USD",
                total_amount=700,
                operations_count=1,
                commission_amount=0,
                status=BillingSummaryStatus.FINALIZED,
            ),
        ]
    )
    session.commit()

    response = admin_client.post("/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()})

    assert response.status_code == 200
    body = response.json()
    assert body == {"clearing_date": target_date.isoformat(), "created": 2}

    stored_batches = session.query(Clearing).filter(Clearing.batch_date == target_date).all()
    assert len(stored_batches) == 2
    assert {(item.merchant_id, item.currency, item.total_amount) for item in stored_batches} == {
        ("m-one", "RUB", 500),
        ("m-two", "USD", 700),
    }

    job_runs = session.query(BillingJobRun).filter(BillingJobRun.job_type == BillingJobType.CLEARING).all()
    assert len(job_runs) == 1
    assert job_runs[0].status == BillingJobStatus.SUCCESS
    assert job_runs[0].metrics == {"created": 2}
