import os
from datetime import date, datetime, timedelta, timezone
from typing import Tuple

import pytest
from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure Celery is disabled for tests so the local evaluator is used
os.environ["DISABLE_CELERY"] = "1"

from app import models  # noqa: F401
from app.api.v1.endpoints.admin_clearing import router as admin_router
from app.db import Base, get_db
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.billing_summary import BillingSummary
from app.models.clearing import Clearing
from app.models.operation import ProductType


@pytest.fixture()
def admin_client(admin_auth_headers: dict) -> Tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(admin_router, prefix="/api/v1")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        client.headers.update(admin_auth_headers)
        yield client, TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _create_batch(db: Session, **kwargs) -> Clearing:
    batch = Clearing(**kwargs)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def _create_period(db: Session, target_date: date) -> BillingPeriod:
    period = BillingPeriod(
        period_type=BillingPeriodType.DAILY,
        start_at=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=BillingPeriodStatus.OPEN,
    )
    db.add(period)
    db.flush()
    return period


def test_listing_with_filters(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client

    with SessionLocal() as db:
        _create_batch(
            db,
            batch_date=date(2025, 12, 4),
            merchant_id="m1",
            currency="RUB",
            total_amount=54321,
            status="PENDING",
        )
        _create_batch(
            db,
            batch_date=date(2025, 11, 30),
            merchant_id="m1",
            currency="RUB",
            total_amount=100,
            status="PENDING",
        )
        _create_batch(
            db,
            batch_date=date(2025, 12, 5),
            merchant_id="m2",
            currency="USD",
            total_amount=200,
            status="PENDING",
        )

    resp = client.get(
        "/api/v1/admin/clearing/batches",
        params={
            "merchant_id": "m1",
            "status": "PENDING",
            "date_from": "2025-12-01",
            "date_to": "2025-12-31",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["merchant_id"] == "m1"
    assert data["items"][0]["status"] == "PENDING"


def test_pagination(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client

    with SessionLocal() as db:
        for i in range(3):
            _create_batch(
                db,
                batch_date=date(2025, 12, 4) + timedelta(days=i),
                merchant_id="m1",
                currency="RUB",
                total_amount=100 + i,
                status="PENDING",
                created_at=datetime(2025, 12, 4, 12, 0, i),
            )

    resp = client.get(
        "/api/v1/admin/clearing/batches",
        params={"limit": 1, "offset": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    # Ordered by batch_date descending
    assert data["items"][0]["batch_date"] == "2025-12-05"


def test_details_endpoint(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client

    with SessionLocal() as db:
        batch = _create_batch(
            db,
            batch_date=date(2025, 12, 6),
            merchant_id="m3",
            currency="RUB",
            total_amount=999,
            status="PENDING",
            details=[{"id": "s1", "total_amount": 999}],
        )

    resp = client.get(f"/api/v1/admin/clearing/batches/{batch.id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["id"] == batch.id
    assert payload["details"] == [{"id": "s1", "total_amount": 999}]


def test_run_clearing_idempotent(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client
    target_date = date(2024, 1, 2)

    with SessionLocal() as db:
        period = _create_period(db, target_date)
        db.add_all(
            [
                BillingSummary(
                    id="s1",
                    billing_date=target_date,
                    billing_period_id=period.id,
                    client_id="c1",
                    merchant_id="m1",
                    product_type=ProductType.AI92,
                    currency="RUB",
                    total_amount=500,
                    total_captured_amount=500,
                    operations_count=1,
                    commission_amount=5,
                ),
                BillingSummary(
                    id="s2",
                    billing_date=target_date,
                    billing_period_id=period.id,
                    client_id="c2",
                    merchant_id="m1",
                    product_type=ProductType.AI95,
                    currency="RUB",
                    total_amount=700,
                    total_captured_amount=700,
                    operations_count=1,
                    commission_amount=7,
                ),
            ]
        )
        db.commit()

    resp = client.post("/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["total_amount"] == 1200

    resp_repeat = client.post("/api/v1/admin/clearing/run", params={"clearing_date": target_date.isoformat()})
    assert resp_repeat.status_code == 200
    assert resp_repeat.json()["total"] == 1