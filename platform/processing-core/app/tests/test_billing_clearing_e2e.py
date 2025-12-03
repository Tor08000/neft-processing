import os
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_CELERY", "1")

from app.db import Base, engine
from app.main import app
from app.services import limits as limits_service


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_billing_and_clearing_pipeline(admin_auth_headers):
    today = date.today()
    with TestClient(app) as client:
        limits_service.celery_app = None
        auth_resp = client.post(
            "/api/v1/processing/terminal-auth",
            json={
                "merchant_id": "m-1",
                "terminal_id": "t-1",
                "client_id": "c-1",
                "card_id": "card-1",
                "amount": 1500,
                "currency": "RUB",
            },
        )
        assert auth_resp.status_code == 200
        auth_id = auth_resp.json()["operation_id"]

        capture_resp = client.post(
            f"/api/v1/transactions/{auth_id}/capture",
            json={"amount": 1500},
        )
        assert capture_resp.status_code == 200
        capture_id = capture_resp.json()["operation_id"]

        summary_resp = client.post(
            "/api/v1/reports/billing/summary/rebuild",
            params={
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
                "merchant_id": "m-1",
            },
        )
        assert summary_resp.status_code == 200
        summaries = summary_resp.json()
        assert len(summaries) == 1
        assert summaries[0]["total_captured_amount"] == 1500
        assert summaries[0]["operations_count"] == 1

        admin_summary = client.get(
            "/api/v1/admin/billing/summary",
            params={
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
                "status": "PENDING",
            },
            headers=admin_auth_headers,
        )
        assert admin_summary.status_code == 200
        assert len(admin_summary.json()) == 1

        batch_resp = client.post(
            "/api/v1/admin/clearing/batches/build",
            json={
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
                "merchant_id": "m-1",
            },
            headers=admin_auth_headers,
        )
        assert batch_resp.status_code == 200
        batch = batch_resp.json()
        assert batch["operations_count"] == 1
        assert batch["total_amount"] == 1500

        operations_resp = client.get(
            f"/api/v1/admin/clearing/batches/{batch['id']}/operations",
            headers=admin_auth_headers,
        )
        assert operations_resp.status_code == 200
        batch_operations = operations_resp.json()
        assert len(batch_operations) == 1
        assert batch_operations[0]["operation_id"] == capture_id

        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        turnover_resp = client.get(
            "/api/v1/reports/turnover",
            params={
                "group_by": "merchant",
                "from": start.isoformat(),
                "to": end.isoformat(),
                "merchant_id": "m-1",
            },
        )
        assert turnover_resp.status_code == 200
        turnover = turnover_resp.json()
        assert turnover["totals"]["captured_amount"] == 1500
        assert turnover["items"][0]["group_key"]["merchant_id"] == "m-1"
