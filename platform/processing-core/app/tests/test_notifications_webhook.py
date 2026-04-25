from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.notifications import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationMessage,
    NotificationPreference,
    NotificationPriority,
    NotificationSubjectType,
    NotificationTemplate,
    NotificationTemplateContentType,
)
from app.services.notifications_v1 import dispatch_pending_notifications, enqueue_notification_message


_TABLES = [
    NotificationTemplate.__table__,
    NotificationPreference.__table__,
    NotificationDelivery.__table__,
    NotificationMessage.__table__,
]


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=_TABLES)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


class _WebhookHandler(BaseHTTPRequestHandler):
    received: dict[str, str | bytes] = {}

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.__class__.received = {
            "body": body,
            "signature": self.headers.get("X-Signature"),
            "content_type": self.headers.get("Content-Type"),
        }
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


@pytest.mark.integration
def test_webhook_notification_delivery(db_session, monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/webhook"
        client_id = str(uuid4())

        template = NotificationTemplate(
            code="webhook_test",
            event_type="WEBHOOK_TEST",
            channel=NotificationChannel.WEBHOOK,
            locale="ru",
            subject=None,
            body="Webhook payload {event}",
            content_type=NotificationTemplateContentType.TEXT,
            required_vars=["event"],
        )
        db_session.add(template)
        preference = NotificationPreference(
            subject_type=NotificationSubjectType.CLIENT,
            subject_id=client_id,
            event_type="WEBHOOK_TEST",
            channel=NotificationChannel.WEBHOOK,
            enabled=True,
            address_override=url,
        )
        db_session.add(preference)
        db_session.commit()

        message = enqueue_notification_message(
            db_session,
            event_type="WEBHOOK_TEST",
            subject_type=NotificationSubjectType.CLIENT,
            subject_id=client_id,
            channels=[NotificationChannel.WEBHOOK],
            template_code="webhook_test",
            template_vars={"event": "ping"},
            priority=NotificationPriority.NORMAL,
            dedupe_key=f"webhook:{uuid4()}",
        )
        db_session.commit()

        monkeypatch.setenv("WEBHOOK_SIGNING_SECRET", "secret")
        dispatch_pending_notifications(db_session)
        db_session.commit()

        delivery = (
            db_session.query(NotificationDelivery)
            .filter(NotificationDelivery.message_id == message.id)
            .filter(NotificationDelivery.channel == NotificationChannel.WEBHOOK)
            .one()
        )
        assert delivery.status == NotificationDeliveryStatus.SENT

        received = _WebhookHandler.received
        body = received.get("body")
        assert isinstance(body, (bytes, bytearray))
        payload = json.loads(body)
        assert payload["event_type"] == "WEBHOOK_TEST"
        assert payload["message_id"] == str(message.id)
        signature = received.get("signature")
        expected = hashlib.sha256(b"secret" + body).hexdigest()
        assert signature == expected
    finally:
        server.shutdown()
        server.server_close()
