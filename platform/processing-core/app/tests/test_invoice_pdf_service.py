from __future__ import annotations

from datetime import date

import pytest

boto3 = pytest.importorskip("boto3")
botocore = pytest.importorskip("botocore")
from botocore.stub import ANY, Stubber
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.invoice import Invoice, InvoiceLine, InvoicePdfStatus
from app.services.invoice_pdf import InvoicePdfService


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # register models
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_generate_invoice_pdf_marks_ready(session):
    invoice = Invoice(
        client_id="client-1",
        period_from=date(2024, 5, 1),
        period_to=date(2024, 5, 31),
        currency="RUB",
        total_amount=1000,
        tax_amount=0,
        total_with_tax=1000,
        pdf_status=InvoicePdfStatus.NONE,
    )
    invoice.lines = [
        InvoiceLine(
            product_id="fuel",
            line_amount=1000,
            tax_amount=0,
            operation_id="op-1",
        )
    ]
    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    service = InvoicePdfService(session)
    key = service._pdf_key(invoice)

    with Stubber(service._s3) as stubber:
        stubber.add_response(
            "put_object",
            {},
            {
                "Bucket": service.bucket,
                "Key": key,
                "Body": ANY,
                "ContentType": "application/pdf",
            },
        )
        generated = service.generate(invoice)
        session.commit()

    assert generated.pdf_status == InvoicePdfStatus.READY
    assert generated.pdf_url == f"s3://{service.bucket}/{key}"
    assert generated.pdf_hash
