from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.operation import Operation, OperationStatus, OperationType
from app.services.abac.engine import AbacDecision, AbacEngine
from app.services.decision import DecisionEngine, DecisionOutcome

from ._money_router_harness import PAYOUT_TEST_TABLES, money_session_context, payout_client_context


class _InMemoryS3Storage:
    _objects: dict[tuple[str, str], bytes] = {}

    def __init__(self, *, bucket: str | None = None):
        self.bucket = bucket or "neft-payouts"

    def put_bytes(self, key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> str:
        self._objects[(self.bucket, key)] = payload
        return f"s3://{self.bucket}/{key}"

    def exists(self, key: str) -> bool:
        return (self.bucket, key) in self._objects

    def get_bytes(self, key: str) -> bytes | None:
        return self._objects.get((self.bucket, key))


@pytest.fixture(autouse=True)
def _stub_policy_and_storage(monkeypatch: pytest.MonkeyPatch):
    from app.api.v1.endpoints import payouts as payouts_api
    from app.services import payout_exports as payout_exports_service

    monkeypatch.setattr(
        DecisionEngine,
        "evaluate",
        lambda *_args, **_kwargs: SimpleNamespace(outcome=DecisionOutcome.ALLOW),
    )
    monkeypatch.setattr(
        AbacEngine,
        "evaluate",
        lambda *_args, **_kwargs: AbacDecision(True, None, [], {"result": True}),
    )
    _InMemoryS3Storage._objects = {}
    monkeypatch.setattr(payout_exports_service, "S3Storage", _InMemoryS3Storage)
    monkeypatch.setattr(payouts_api, "S3Storage", _InMemoryS3Storage)


@pytest.fixture
def session() -> Session:
    with money_session_context(tables=PAYOUT_TEST_TABLES) as db:
        yield db


@pytest.fixture
def admin_client(session: Session) -> TestClient:
    with payout_client_context(db_session=session) as api_client:
        yield api_client


def _seed_captured_operations(db: Session, target_date: date, partner_id: str, count: int = 3) -> None:
    base_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    for idx in range(count):
        amount = 1000 + idx * 100
        db.add(
            Operation(
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
        )
    db.commit()


def _seed_billing_period(db: Session, target_date: date, status: BillingPeriodStatus) -> None:
    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=status,
    )
    db.add(period)
    db.commit()


def test_payout_close_period_idempotent(admin_client: TestClient, session: Session):
    target_date = date.today()
    _seed_captured_operations(session, target_date, "partner-1")
    _seed_billing_period(session, target_date, BillingPeriodStatus.FINALIZED)

    payload = {
        "tenant_id": 1,
        "partner_id": "partner-1",
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    first = admin_client.post("/api/v1/payouts/close-period", json=payload)
    assert first.status_code == 200
    first_body = first.json()

    second = admin_client.post("/api/v1/payouts/close-period", json=payload)
    assert second.status_code == 200
    second_body = second.json()

    assert first_body["batch_id"] == second_body["batch_id"]
    assert first_body["items_count"] == 1
    assert second_body["items_count"] == 1


def test_payout_state_transitions(session: Session):
    target_date = date.today()
    _seed_captured_operations(session, target_date, "partner-1")
    _seed_billing_period(session, target_date, BillingPeriodStatus.FINALIZED)

    with payout_client_context(db_session=session) as finance_client:
        payload = {
            "tenant_id": 1,
            "partner_id": "partner-1",
            "date_from": target_date.isoformat(),
            "date_to": target_date.isoformat(),
        }
        close_resp = finance_client.post("/api/v1/payouts/close-period", json=payload)
        batch_id = close_resp.json()["batch_id"]

        settle_without_sent = finance_client.post(
            f"/api/v1/payouts/batches/{batch_id}/mark-settled",
            json={"provider": "bank", "external_ref": "BANK-REF-1"},
        )
        assert settle_without_sent.status_code == 403

        sent_resp = finance_client.post(
            f"/api/v1/payouts/batches/{batch_id}/mark-sent",
            json={"provider": "bank", "external_ref": "BANK-REF-1"},
        )
        assert sent_resp.status_code == 200
        assert sent_resp.json()["state"] == "SENT"

        sent_again = finance_client.post(
            f"/api/v1/payouts/batches/{batch_id}/mark-sent",
            json={"provider": "bank", "external_ref": "BANK-REF-1"},
        )
        assert sent_again.status_code == 200

    with payout_client_context(
        db_session=session,
        token_claims={"roles": ["SUPERADMIN"], "sub": "admin-2", "user_id": "admin-2", "tenant_id": "1"},
    ) as superadmin_client:
        settled_resp = superadmin_client.post(
            f"/api/v1/payouts/batches/{batch_id}/mark-settled",
            json={"provider": "bank", "external_ref": "BANK-REF-1"},
        )
        assert settled_resp.status_code == 200
        assert settled_resp.json()["state"] == "SETTLED"


def test_payout_reconcile_ok(admin_client: TestClient, session: Session):
    target_date = date.today()
    _seed_captured_operations(session, target_date, "partner-1")
    _seed_billing_period(session, target_date, BillingPeriodStatus.FINALIZED)

    payload = {
        "tenant_id": 1,
        "partner_id": "partner-1",
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    close_resp = admin_client.post("/api/v1/payouts/close-period", json=payload)
    batch_id = close_resp.json()["batch_id"]

    reconcile_resp = admin_client.get(f"/api/v1/payouts/batches/{batch_id}/reconcile")
    assert reconcile_resp.status_code == 200
    body = reconcile_resp.json()
    assert body["status"] == "OK"
    assert body["diff"]["amount"] == "0.00"
    assert body["diff"]["count"] == 0


def test_payout_unique_external_ref(admin_client: TestClient, session: Session):
    target_date = date.today()
    _seed_captured_operations(session, target_date, "partner-1")
    _seed_captured_operations(session, target_date, "partner-2")
    _seed_billing_period(session, target_date, BillingPeriodStatus.FINALIZED)

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
    batch_one = admin_client.post("/api/v1/payouts/close-period", json=payload_one).json()["batch_id"]
    batch_two = admin_client.post("/api/v1/payouts/close-period", json=payload_two).json()["batch_id"]

    first_mark = admin_client.post(
        f"/api/v1/payouts/batches/{batch_one}/mark-sent",
        json={"provider": "bank", "external_ref": "BANK-UNIQ-1"},
    )
    assert first_mark.status_code == 200

    second_mark = admin_client.post(
        f"/api/v1/payouts/batches/{batch_two}/mark-sent",
        json={"provider": "bank", "external_ref": "BANK-UNIQ-1"},
    )
    assert second_mark.status_code == 409
