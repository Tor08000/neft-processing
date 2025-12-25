import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

os.environ.setdefault("DISABLE_CELERY", "1")
os.environ.setdefault("NEFT_S3_ENDPOINT", "http://minio:9000")
os.environ.setdefault("NEFT_S3_ACCESS_KEY", "change-me")
os.environ.setdefault("NEFT_S3_SECRET_KEY", "change-me")
os.environ.setdefault("NEFT_S3_BUCKET_PAYOUTS", "neft-payouts")
os.environ.setdefault("NEFT_S3_REGION", "us-east-1")

from app.config import settings
from app.db import Base, engine, get_sessionmaker
from app.main import app
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.payout_batch import PayoutBatch
from app.services.payout_export_xlsx import load_bank_format
from app.services.s3_storage import S3Storage


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


def _create_batch(client: TestClient, target_date: date, partner_id: str) -> str:
    _seed_captured_operations(target_date, partner_id)
    _seed_billing_period(target_date, BillingPeriodStatus.FINALIZED)
    payload = {
        "tenant_id": 1,
        "partner_id": partner_id,
        "date_from": target_date.isoformat(),
        "date_to": target_date.isoformat(),
    }
    response = client.post("/api/v1/payouts/close-period", json=payload)
    assert response.status_code == 200
    return response.json()["batch_id"]


def _seed_partner_meta(batch_id: str) -> None:
    session = get_sessionmaker()()
    batch = session.query(PayoutBatch).filter(PayoutBatch.id == batch_id).one()
    batch.meta = {
        "partner": {
            "name": "ООО Тест",
            "inn": "7701234567",
            "bank": {"bik": "044525225", "account": "40702810900000000001"},
        }
    }
    session.commit()
    session.close()


def test_payout_export_xlsx_idempotent():
    target_date = date.today()
    with TestClient(app) as client:
        batch_id = _create_batch(client, target_date, "partner-xlsx-1")
        _seed_partner_meta(batch_id)

        payload = {
            "format": "XLSX",
            "bank_format_code": "SBER_REGISTRY_V1",
            "provider": "bank",
            "external_ref": "BANK-REG-101",
        }
        first = client.post(f"/api/v1/payouts/batches/{batch_id}/export", json=payload)
        assert first.status_code == 200
        first_body = first.json()

        second = client.post(f"/api/v1/payouts/batches/{batch_id}/export", json=payload)
        assert second.status_code == 200
        second_body = second.json()

        assert first_body["export_id"] == second_body["export_id"]
        assert first_body["object_key"] == second_body["object_key"]
        assert first_body["state"] == "UPLOADED"

        storage = S3Storage(bucket=settings.NEFT_S3_BUCKET_PAYOUTS)
        assert storage.exists(first_body["object_key"])


def test_payout_export_xlsx_download_content(admin_auth_headers):
    target_date = date.today()
    with TestClient(app) as client:
        batch_id = _create_batch(client, target_date, "partner-xlsx-2")
        _seed_partner_meta(batch_id)

        payload = {
            "format": "XLSX",
            "bank_format_code": "SBER_REGISTRY_V1",
            "provider": "bank",
            "external_ref": "BANK-REG-102",
        }
        create_resp = client.post(f"/api/v1/payouts/batches/{batch_id}/export", json=payload)
        assert create_resp.status_code == 200
        export_id = create_resp.json()["export_id"]

        download_resp = client.get(
            f"/api/v1/payouts/exports/{export_id}/download",
            headers=admin_auth_headers,
        )
        assert download_resp.status_code == 200
        assert download_resp.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert download_resp.content

        bank_format = load_bank_format("SBER_REGISTRY_V1")
        workbook = load_workbook(filename=BytesIO(download_resp.content))
        worksheet = workbook.active
        assert worksheet.title == bank_format.sheet_name
        headers = [worksheet.cell(row=1, column=idx + 1).value for idx in range(len(bank_format.columns))]
        expected_headers = [column.header for column in bank_format.columns]
        assert headers == expected_headers
        session = get_sessionmaker()()
        items = session.query(PayoutBatch).filter(PayoutBatch.id == batch_id).one().items
        session.close()
        assert worksheet.max_row == 1 + len(items)


def test_payout_export_xlsx_external_ref_conflict():
    target_date = date.today()
    with TestClient(app) as client:
        batch_one = _create_batch(client, target_date, "partner-xlsx-3")
        batch_two = _create_batch(client, target_date, "partner-xlsx-4")
        _seed_partner_meta(batch_two)

        payload_csv = {"format": "CSV", "provider": "bank", "external_ref": "BANK-REG-103"}
        first = client.post(f"/api/v1/payouts/batches/{batch_one}/export", json=payload_csv)
        assert first.status_code == 200

        payload_xlsx = {
            "format": "XLSX",
            "bank_format_code": "SBER_REGISTRY_V1",
            "provider": "bank",
            "external_ref": "BANK-REG-103",
        }
        conflict = client.post(f"/api/v1/payouts/batches/{batch_two}/export", json=payload_xlsx)
        assert conflict.status_code == 409
