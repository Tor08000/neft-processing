import os
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_CELERY", "1")
os.environ.setdefault("NEFT_S3_ENDPOINT", "http://minio:9000")
os.environ.setdefault("NEFT_S3_ACCESS_KEY", "change-me")
os.environ.setdefault("NEFT_S3_SECRET_KEY", "change-me")
os.environ.setdefault("NEFT_S3_BUCKET_DOCUMENTS", "neft-documents")
os.environ.setdefault("NEFT_S3_REGION", "us-east-1")

from app.db import Base, engine, get_sessionmaker
from app.main import app
from app.models.documents import Document, DocumentFile
from app.models.finance import CreditNote, InvoicePayment
from app.models.invoice import Invoice, InvoiceStatus
from app.services.documents_storage import DocumentsStorage


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_invoice(client_id: str, period_from: date, period_to: date) -> str:
    session = get_sessionmaker()()
    invoice_id = str(uuid4())
    invoice = Invoice(
        id=invoice_id,
        client_id=client_id,
        number=f"INV-{invoice_id[:8]}",
        period_from=period_from,
        period_to=period_to,
        currency="RUB",
        status=InvoiceStatus.SENT,
        total_amount=10000,
        tax_amount=2000,
        total_with_tax=12000,
        amount_paid=5000,
        amount_due=7000,
        amount_refunded=0,
        issued_at=datetime.now(timezone.utc),
    )
    session.add(invoice)
    session.add(
        InvoicePayment(
            id=uuid4(),
            invoice_id=invoice_id,
            amount=5000,
            currency="RUB",
            idempotency_key=f"pay-{invoice_id}",
        )
    )
    session.add(
        CreditNote(
            id=uuid4(),
            invoice_id=invoice_id,
            amount=1000,
            currency="RUB",
            idempotency_key=f"refund-{invoice_id}",
        )
    )
    session.commit()
    session.close()
    return invoice_id


def _generate_package(client, admin_headers, payload):
    response = client.post("/api/v1/admin/closing-packages/generate", json=payload, headers=admin_headers)
    assert response.status_code == 200
    return response.json()


def test_closing_package_generate_and_download_e2e(make_jwt):
    period_from = date(2025, 12, 1)
    period_to = date(2025, 12, 31)
    client_id = "client-1"
    _seed_invoice(client_id, period_from, period_to)

    admin_token = make_jwt(roles=("ADMIN",))
    client_token = make_jwt(roles=("CLIENT_USER",), client_id=client_id)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    client_headers = {"Authorization": f"Bearer {client_token}"}

    payload = {
        "client_id": client_id,
        "date_from": period_from.isoformat(),
        "date_to": period_to.isoformat(),
        "version_mode": "AUTO",
        "force_new_version": False,
        "tenant_id": 1,
    }

    with TestClient(app) as api_client:
        result = _generate_package(api_client, admin_headers, payload)
        assert result["version"] == 1
        assert len(result["documents"]) == 3

        session = get_sessionmaker()()
        documents = session.query(Document).all()
        files = session.query(DocumentFile).all()
        assert len(documents) == 3
        assert len(files) == 6

        storage = DocumentsStorage()
        for document in documents:
            for file in document.files:
                assert storage.exists(file.object_key)

            pdf_resp = api_client.get(
                f"/api/v1/client/documents/{document.id}/download",
                params={"file_type": "PDF"},
                headers=client_headers,
            )
            assert pdf_resp.status_code == 200
            assert pdf_resp.headers["content-type"] == "application/pdf"
            assert len(pdf_resp.content) > 0

            xlsx_resp = api_client.get(
                f"/api/v1/client/documents/{document.id}/download",
                params={"file_type": "XLSX"},
                headers=client_headers,
            )
            assert xlsx_resp.status_code == 200
            assert (
                xlsx_resp.headers["content-type"]
                == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            assert len(xlsx_resp.content) > 0

        session.close()


def test_versioning_regeneration(make_jwt):
    period_from = date(2025, 11, 1)
    period_to = date(2025, 11, 30)
    client_id = "client-2"
    _seed_invoice(client_id, period_from, period_to)

    admin_token = make_jwt(roles=("ADMIN",))
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "client_id": client_id,
        "date_from": period_from.isoformat(),
        "date_to": period_to.isoformat(),
        "version_mode": "AUTO",
        "force_new_version": False,
        "tenant_id": 1,
    }

    with TestClient(app) as api_client:
        first = _generate_package(api_client, admin_headers, payload)
        second = _generate_package(api_client, admin_headers, payload)
        assert first["package_id"] == second["package_id"]
        assert first["version"] == second["version"] == 1

        payload["force_new_version"] = True
        third = _generate_package(api_client, admin_headers, payload)
        assert third["version"] == 2

        session = get_sessionmaker()()
        documents = session.query(Document).filter(Document.client_id == client_id).all()
        versions = {doc.version for doc in documents}
        assert versions == {1, 2}

        storage = DocumentsStorage()
        for document in documents:
            for file in document.files:
                assert storage.exists(file.object_key)

        session.close()


def test_client_scope_protection(make_jwt):
    period_from = date(2025, 10, 1)
    period_to = date(2025, 10, 31)
    client_id = "client-3"
    other_client = "client-4"
    _seed_invoice(client_id, period_from, period_to)

    admin_token = make_jwt(roles=("ADMIN",))
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "client_id": client_id,
        "date_from": period_from.isoformat(),
        "date_to": period_to.isoformat(),
        "version_mode": "AUTO",
        "force_new_version": False,
        "tenant_id": 1,
    }

    with TestClient(app) as api_client:
        result = _generate_package(api_client, admin_headers, payload)
        document_id = result["documents"][0]["id"]

        other_token = make_jwt(roles=("CLIENT_USER",), client_id=other_client)
        other_headers = {"Authorization": f"Bearer {other_token}"}
        resp = api_client.get(
            f"/api/v1/client/documents/{document_id}/download",
            params={"file_type": "PDF"},
            headers=other_headers,
        )
        assert resp.status_code == 403
