from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.clearing_batch import ClearingBatch
from app.models.clearing_batch_operation import ClearingBatchOperation

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


def _create_batch(db: Session, **kwargs) -> ClearingBatch:
    batch = ClearingBatch(**kwargs)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def test_listing_with_filters(admin_client: TestClient, session: Session):
    _create_batch(
        session,
        date_from=date(2025, 12, 4),
        date_to=date(2025, 12, 4),
        merchant_id="m1",
        total_amount=54321,
        status="PENDING",
        operations_count=2,
    )
    _create_batch(
        session,
        date_from=date(2025, 11, 30),
        date_to=date(2025, 11, 30),
        merchant_id="m1",
        total_amount=100,
        status="PENDING",
        operations_count=1,
    )
    _create_batch(
        session,
        date_from=date(2025, 12, 5),
        date_to=date(2025, 12, 5),
        merchant_id="m2",
        total_amount=200,
        status="PENDING",
        operations_count=1,
    )

    resp = admin_client.get(
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
    assert len(data) == 1
    assert data[0]["merchant_id"] == "m1"
    assert data[0]["status"] == "PENDING"
    assert data[0]["date_from"] == "2025-12-04"
    assert data[0]["date_to"] == "2025-12-04"


def test_pagination(admin_client: TestClient, session: Session):
    for i in range(3):
        _create_batch(
            session,
            date_from=date(2025, 12, 4) + timedelta(days=i),
            date_to=date(2025, 12, 4) + timedelta(days=i),
            merchant_id="m1",
            total_amount=100 + i,
            status="PENDING",
            operations_count=1,
            created_at=datetime(2025, 12, 4, 12, 0, i),
        )

    resp = admin_client.get(
        "/api/v1/admin/clearing/batches",
        params={"limit": 1, "offset": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["date_from"] == "2025-12-05"
    assert data[0]["date_to"] == "2025-12-05"


def test_details_endpoint(admin_client: TestClient, session: Session):
    batch = _create_batch(
        session,
        date_from=date(2025, 12, 6),
        date_to=date(2025, 12, 6),
        merchant_id="m3",
        total_amount=999,
        status="PENDING",
        operations_count=1,
    )
    session.add_all(
        [
            ClearingBatchOperation(batch_id=batch.id, operation_id="op-1", amount=999),
        ]
    )
    session.execute(text("INSERT INTO operations (operation_id) VALUES ('op-1')"))
    session.commit()

    resp = admin_client.get(f"/api/v1/admin/clearing/batches/{batch.id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["id"] == batch.id
    assert payload["date_from"] == "2025-12-06"
    assert payload["date_to"] == "2025-12-06"
    assert payload["operations"][0]["operation_id"] == "op-1"


def test_mark_sent_and_confirmed(admin_client: TestClient, session: Session):
    batch = _create_batch(
        session,
        date_from=date(2025, 12, 7),
        date_to=date(2025, 12, 7),
        merchant_id="m4",
        total_amount=1500,
        status="PENDING",
        operations_count=2,
    )

    mark_sent = admin_client.post(f"/api/v1/admin/clearing/batches/{batch.id}/mark-sent")
    assert mark_sent.status_code == 200
    assert mark_sent.json()["status"] == "SENT"

    mark_confirmed = admin_client.post(f"/api/v1/admin/clearing/batches/{batch.id}/mark-confirmed")
    assert mark_confirmed.status_code == 200
    assert mark_confirmed.json()["status"] == "CONFIRMED"
