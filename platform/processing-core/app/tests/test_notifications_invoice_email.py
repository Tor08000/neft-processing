from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest

from app.db import Base, SessionLocal, engine
from app.models.client import Client
from app.models.notifications import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationMessage,
    NotificationTemplate,
    NotificationTemplateContentType,
)
from app.services.billing_service import issue_invoice
from app.services.notifications_v1 import dispatch_pending_notifications
from app.services.case_events_service import CaseEventActor


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.integration
def test_invoice_notification_sends_email(db_session, monkeypatch):
    client_id = str(uuid4())
    client = Client(id=UUID(client_id), name="Acme Fuel", email="billing@acme.test")
    db_session.add(client)

    template = NotificationTemplate(
        code="invoice_issued_email",
        event_type="INVOICE_ISSUED",
        channel=NotificationChannel.EMAIL,
        locale="ru",
        subject="Invoice {invoice_number}",
        body="Hello {client_name}, invoice {invoice_number} amount {amount}",
        content_type=NotificationTemplateContentType.TEXT,
        required_vars=["invoice_number", "client_name", "amount"],
    )
    db_session.add(template)
    db_session.commit()

    actor = CaseEventActor(id="user-1", email="ops@example.com")
    result = issue_invoice(
        db_session,
        tenant_id=1,
        client_id=client_id,
        case_id=None,
        currency="RUB",
        amount_total=Decimal("150.00"),
        due_at=datetime.now(timezone.utc),
        idempotency_key="invoice-email-1",
        actor=actor,
        request_id="req-1",
        trace_id="trace-1",
    )
    db_session.commit()

    outbox = (
        db_session.query(NotificationMessage)
        .filter(NotificationMessage.event_type == "INVOICE_ISSUED")
        .filter(NotificationMessage.subject_id == client_id)
        .one()
    )
    assert outbox.template_code == "invoice_issued_email"

    monkeypatch.setenv("SMTP_HOST", "mailpit")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_TLS", "false")
    monkeypatch.setenv("SMTP_FROM", "no-reply@neft.local")

    mailpit_url = "http://mailpit:8025/api/v1/messages"
    try:
        httpx.get(mailpit_url, timeout=5)
    except httpx.RequestError:
        pytest.skip("mailpit not available")
    dispatch_pending_notifications(db_session)
    db_session.commit()

    delivery = (
        db_session.query(NotificationDelivery)
        .filter(NotificationDelivery.message_id == outbox.id)
        .filter(NotificationDelivery.channel == NotificationChannel.EMAIL)
        .one()
    )
    assert delivery.status == NotificationDeliveryStatus.SENT

    response = httpx.get(mailpit_url, timeout=5)
    assert response.status_code == 200
    items = response.json().get("messages", [])
    assert items
    latest = items[0]
    assert result.invoice.invoice_number in latest.get("Subject", "")
