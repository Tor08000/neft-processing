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
    existing = (
        db.query(BillingPeriod)
        .filter(BillingPeriod.period_type == BillingPeriodType.ADHOC)
        .filter(BillingPeriod.start_at == datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc))
        .filter(BillingPeriod.end_at == datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc))
        .one_or_none()
    )
    if existing:
        existing.status = status
        db.commit()
        return
    period = BillingPeriod(
        period_type=BillingPeriodType.ADHOC,
        start_at=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        end_at=datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc),
        tz="UTC",
        status=status,
    )
    db.add(period)
    db.commit()


def _create_batch(client: TestClient, db: Session, target_date: date, partner_id: str) -> str:
    _seed_captured_operations(db, target_date, partner_id)
    _seed_billing_period(db, target_date, BillingPeriodStatus.FINALIZED)
    payload = {
        "tenant_id": 1,
        "partner_id": partner_id,
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    response = client.post("/api/v1/payouts/close-period", json=payload)
    assert response.status_code == 200
    return response.json()["batch_id"]


def test_payout_export_idempotent(admin_client: TestClient, session: Session):
    target_date = date.today()
    batch_id = _create_batch(admin_client, session, target_date, "partner-1")

    payload = {"format": "CSV", "provider": "bank", "external_ref": "BANK-REG-001"}
    first = admin_client.post(f"/api/v1/payouts/batches/{batch_id}/export", json=payload)
    assert first.status_code == 200
    first_body = first.json()

    second = admin_client.post(f"/api/v1/payouts/batches/{batch_id}/export", json=payload)
    assert second.status_code == 200
    second_body = second.json()

    assert first_body["export_id"] == second_body["export_id"]
    assert first_body["object_key"] == second_body["object_key"]
    assert first_body["state"] == "UPLOADED"

    storage = _InMemoryS3Storage(bucket=first_body["bucket"])
    assert storage.exists(first_body["object_key"])


def test_payout_export_download_returns_bytes(admin_client: TestClient, session: Session):
    target_date = date.today()
    batch_id = _create_batch(admin_client, session, target_date, "partner-2")
    payload = {"format": "CSV", "provider": "bank", "external_ref": "BANK-REG-002"}
    create_resp = admin_client.post(f"/api/v1/payouts/batches/{batch_id}/export", json=payload)
    assert create_resp.status_code == 200
    export_id = create_resp.json()["export_id"]

    list_resp = admin_client.get(f"/api/v1/payouts/batches/{batch_id}/exports")
    assert list_resp.status_code == 200
    assert list_resp.json()["items"][0]["export_id"] == export_id

    download_resp = admin_client.get(f"/api/v1/payouts/exports/{export_id}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"].startswith("text/csv")
    assert download_resp.content
    assert b"item_id" in download_resp.content


def test_payout_export_external_ref_conflict(admin_client: TestClient, session: Session):
    target_date = date.today()
    batch_one = _create_batch(admin_client, session, target_date, "partner-3")
    batch_two = _create_batch(admin_client, session, target_date, "partner-4")

    payload = {"format": "CSV", "provider": "bank", "external_ref": "BANK-REG-003"}
    first = admin_client.post(f"/api/v1/payouts/batches/{batch_one}/export", json=payload)
    assert first.status_code == 200

    conflict = admin_client.post(f"/api/v1/payouts/batches/{batch_two}/export", json=payload)
    assert conflict.status_code == 409


def test_payout_export_requires_finance_role(session: Session):
    target_date = date.today()
    with payout_client_context(db_session=session) as finance_client:
        batch_id = _create_batch(finance_client, session, target_date, "partner-5")

    with payout_client_context(
        db_session=session,
        token_claims={"roles": ["ADMIN"], "sub": "admin-only", "user_id": "admin-only", "tenant_id": "1"},
    ) as admin_only_client:
        payload = {"format": "CSV", "provider": "bank", "external_ref": "BANK-REG-004"}
        response = admin_only_client.post(f"/api/v1/payouts/batches/{batch_id}/export", json=payload)
        assert response.status_code == 403
