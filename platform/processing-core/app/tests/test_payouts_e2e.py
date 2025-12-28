from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, get_sessionmaker
from app.main import app
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.payout_batch import PayoutItem


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_captured_operations(target_date: date, partner_id: str, count: int = 3) -> None:
    session = get_sessionmaker()()
    base_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    for idx in range(count):
        amount = 1000 + idx * 100
        op = Operation(
            ext_operation_id=f"seed-op-{partner_id}-{idx}",
            operation_type=OperationType.COMMIT,
            status=OperationStatus.CAPTURED,
            created_at=base_dt + timedelta(hours=idx + 1),
            updated_at=base_dt + timedelta(hours=idx + 1),
            merchant_id=partner_id,
            terminal_id="terminal-1",
            client_id="client-1",
            card_id="card-1",
            product_id="FUEL",
            amount=amount,
            amount_settled=amount,
            currency="RUB",
            quantity=Decimal("1.0"),
            captured_amount=amount,
            refunded_amount=0,
            response_code="00",
            response_message="OK",
            authorized=True,
        )
        session.add(op)
    session.commit()
    session.close()


def _seed_billing_period(target_date: date, status: BillingPeriodStatus) -> None:
    session = get_sessionmaker()()
    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=status,
    )
    session.add(period)
    session.commit()
    session.close()


def test_payout_close_period_idempotent(admin_auth_headers):
    target_date = date.today()
    _seed_captured_operations(target_date, "partner-1")
    _seed_billing_period(target_date, BillingPeriodStatus.FINALIZED)

    client = TestClient(app)
    payload = {
        "tenant_id": 1,
        "partner_id": "partner-1",
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    first = client.post("/api/v1/payouts/close-period", json=payload, headers=admin_auth_headers)
    assert first.status_code == 200
    first_body = first.json()

    second = client.post("/api/v1/payouts/close-period", json=payload, headers=admin_auth_headers)
    assert second.status_code == 200
    second_body = second.json()

    assert first_body["batch_id"] == second_body["batch_id"]
    assert first_body["items_count"] == 1
    assert second_body["items_count"] == 1

    session = get_sessionmaker()()
    assert session.query(PayoutItem).count() == 1
    session.close()


def test_payout_state_transitions(admin_auth_headers, make_jwt):
    target_date = date.today()
    _seed_captured_operations(target_date, "partner-1")
    _seed_billing_period(target_date, BillingPeriodStatus.FINALIZED)

    client = TestClient(app)
    payload = {
        "tenant_id": 1,
        "partner_id": "partner-1",
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    close_resp = client.post("/api/v1/payouts/close-period", json=payload, headers=admin_auth_headers)
    batch_id = close_resp.json()["batch_id"]

    settle_without_sent = client.post(
        f"/api/v1/payouts/batches/{batch_id}/mark-settled",
        json={"provider": "bank", "external_ref": "BANK-REF-1"},
        headers=admin_auth_headers,
    )
    assert settle_without_sent.status_code == 403

    sent_resp = client.post(
        f"/api/v1/payouts/batches/{batch_id}/mark-sent",
        json={"provider": "bank", "external_ref": "BANK-REF-1"},
        headers=admin_auth_headers,
    )
    assert sent_resp.status_code == 200
    assert sent_resp.json()["state"] == "SENT"

    sent_again = client.post(
        f"/api/v1/payouts/batches/{batch_id}/mark-sent",
        json={"provider": "bank", "external_ref": "BANK-REF-1"},
        headers=admin_auth_headers,
    )
    assert sent_again.status_code == 200

    superadmin_token = make_jwt(roles=("SUPERADMIN",))
    superadmin_headers = {"Authorization": f"Bearer {superadmin_token}"}
    settled_resp = client.post(
        f"/api/v1/payouts/batches/{batch_id}/mark-settled",
        json={"provider": "bank", "external_ref": "BANK-REF-1"},
        headers=superadmin_headers,
    )
    assert settled_resp.status_code == 200
    assert settled_resp.json()["state"] == "SETTLED"


def test_payout_reconcile_ok(admin_auth_headers):
    target_date = date.today()
    _seed_captured_operations(target_date, "partner-1")
    _seed_billing_period(target_date, BillingPeriodStatus.FINALIZED)

    client = TestClient(app)
    payload = {
        "tenant_id": 1,
        "partner_id": "partner-1",
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    close_resp = client.post("/api/v1/payouts/close-period", json=payload, headers=admin_auth_headers)
    batch_id = close_resp.json()["batch_id"]

    reconcile_resp = client.get(f"/api/v1/payouts/batches/{batch_id}/reconcile")
    assert reconcile_resp.status_code == 200
    body = reconcile_resp.json()
    assert body["status"] == "OK"
    assert body["diff"]["amount"] == 0
    assert body["diff"]["count"] == 0


def test_payout_unique_external_ref(admin_auth_headers):
    target_date = date.today()
    _seed_captured_operations(target_date, "partner-1")
    _seed_captured_operations(target_date, "partner-2")
    _seed_billing_period(target_date, BillingPeriodStatus.FINALIZED)

    client = TestClient(app)
    payload_one = {
        "tenant_id": 1,
        "partner_id": "partner-1",
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    payload_two = {
        "tenant_id": 1,
        "partner_id": "partner-2",
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    batch_one = client.post(
        "/api/v1/payouts/close-period",
        json=payload_one,
        headers=admin_auth_headers,
    ).json()["batch_id"]
    batch_two = client.post(
        "/api/v1/payouts/close-period",
        json=payload_two,
        headers=admin_auth_headers,
    ).json()["batch_id"]

    first_mark = client.post(
        f"/api/v1/payouts/batches/{batch_one}/mark-sent",
        json={"provider": "bank", "external_ref": "BANK-UNIQ-1"},
        headers=admin_auth_headers,
    )
    assert first_mark.status_code == 200

    second_mark = client.post(
        f"/api/v1/payouts/batches/{batch_two}/mark-sent",
        json={"provider": "bank", "external_ref": "BANK-UNIQ-1"},
        headers=admin_auth_headers,
    )
    assert second_mark.status_code == 409
