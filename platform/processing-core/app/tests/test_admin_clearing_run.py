from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models.billing_job_run import BillingJobRun, BillingJobType
from app.models.billing_summary import BillingSummary, BillingSummaryStatus
from app.models.clearing import Clearing

pytestmark = pytest.mark.integration


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_client(admin_auth_headers: dict):
    with TestClient(app) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


def _cleanup(session: Session, target_date: date):
    session.query(Clearing).filter(Clearing.batch_date == target_date).delete(synchronize_session=False)
    session.query(BillingSummary).filter(BillingSummary.billing_date == target_date).delete(synchronize_session=False)
    session.query(BillingJobRun).filter(BillingJobRun.job_type == BillingJobType.CLEARING).delete(
        synchronize_session=False
    )
    session.commit()


def test_admin_clearing_no_data(admin_client: TestClient, session: Session):
    target_date = date(2024, 1, 1)
    try:
        response = admin_client.post(
            "/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["created"] == 0
        assert body["reason"] == "no_data"
    finally:
        _cleanup(session, target_date)


def test_admin_clearing_upserts_existing_rows(admin_client: TestClient, session: Session):
    target_date = date(2024, 1, 2)
    clearing = Clearing(batch_date=target_date, merchant_id="m1", currency="RUB", total_amount=0, details=[])
    session.add(clearing)
    session.add(
        BillingSummary(
            billing_date=target_date,
            merchant_id="m1",
            client_id="c1",
            currency="RUB",
            total_amount=500,
            operations_count=1,
            commission_amount=0,
            status=BillingSummaryStatus.FINALIZED,
        )
    )
    session.add(
        BillingSummary(
            billing_date=target_date,
            merchant_id="m2",
            client_id="c2",
            currency="USD",
            total_amount=700,
            operations_count=1,
            commission_amount=0,
            status=BillingSummaryStatus.FINALIZED,
        )
    )
    session.commit()
    try:
        response = admin_client.post(
            "/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["created"] == 1
        assert body["updated"] == 1
        assert not body.get("reason")

        session.expire_all()
        stored = session.query(Clearing).filter(Clearing.batch_date == target_date).all()
        assert len(stored) == 2
        refreshed = [item for item in stored if item.merchant_id == "m1"][0]
        assert refreshed.total_amount == 500
        assert refreshed.details
    finally:
        _cleanup(session, target_date)


def test_admin_clearing_creates_from_summaries(admin_client: TestClient, session: Session):
    target_date = date(2024, 1, 3)
    summaries = [
        BillingSummary(
            billing_date=target_date,
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
            merchant_id="m-one",
            client_id="c2",
            currency="RUB",
            total_amount=700,
            operations_count=1,
            commission_amount=0,
            status=BillingSummaryStatus.FINALIZED,
        ),
    ]
    session.add_all(summaries)
    session.commit()
    try:
        response = admin_client.post(
            "/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["created"] == 1
        assert body["updated"] == 0
        assert body.get("reason") in (None, "")

        stored = session.query(Clearing).filter(Clearing.batch_date == target_date).all()
        assert len(stored) == 1
        assert stored[0].total_amount == 1200

        job_runs = session.query(BillingJobRun).filter(BillingJobRun.job_type == BillingJobType.CLEARING).all()
        assert job_runs
    finally:
        _cleanup(session, target_date)
