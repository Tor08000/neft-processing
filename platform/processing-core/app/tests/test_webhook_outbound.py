from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.fuel import (
    FleetNotificationChannel,
    FleetNotificationChannelStatus,
    FleetNotificationChannelType,
    FleetNotificationEventType,
    FleetNotificationOutbox,
    FleetNotificationOutboxStatus,
    FleetNotificationPolicy,
    FleetNotificationPolicyScopeType,
    FleetNotificationSeverity,
    NotificationDeliveryLog,
    WebhookDeliveryAttempt,
)
from app.services.fleet_notification_dispatcher import _now, dispatch_outbox_item
from app.services.notifications.webhook_signature import verify_webhook_signature


class _WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - handler naming from stdlib
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.received.append({"headers": dict(self.headers), "body": body})
        status = self.server.status_sequence.pop(0) if self.server.status_sequence else 200
        self.send_response(status)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - stdlib signature
        return None


def _start_server(status_sequence: list[int]) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 0), _WebhookHandler)
    server.received = []
    server.status_sequence = list(status_sequence)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    FleetNotificationChannel.__table__.create(bind=engine)
    FleetNotificationPolicy.__table__.create(bind=engine)
    FleetNotificationOutbox.__table__.create(bind=engine)
    NotificationDeliveryLog.__table__.create(bind=engine)
    WebhookDeliveryAttempt.__table__.create(bind=engine)
    session = SessionLocal()
    session._engine = engine
    return session


def _teardown(session: Session) -> None:
    engine = session._engine
    session.close()
    WebhookDeliveryAttempt.__table__.drop(bind=engine)
    NotificationDeliveryLog.__table__.drop(bind=engine)
    FleetNotificationOutbox.__table__.drop(bind=engine)
    FleetNotificationPolicy.__table__.drop(bind=engine)
    FleetNotificationChannel.__table__.drop(bind=engine)
    engine.dispose()


def test_webhook_outbound_signature_and_retry_headers() -> None:
    server = _start_server([500, 200])
    session = _make_session()
    try:
        url = f"http://127.0.0.1:{server.server_port}/webhook"
        channel = FleetNotificationChannel(
            client_id="client-1",
            channel_type=FleetNotificationChannelType.WEBHOOK,
            target=url,
            status=FleetNotificationChannelStatus.ACTIVE,
            secret_ref="secret",
        )
        policy = FleetNotificationPolicy(
            client_id="client-1",
            scope_type=FleetNotificationPolicyScopeType.CLIENT,
            scope_id=None,
            event_type=FleetNotificationEventType.TEST,
            severity_min=FleetNotificationSeverity.LOW,
            channels=[FleetNotificationChannelType.WEBHOOK.value],
            cooldown_seconds=300,
            active=True,
        )
        outbox = FleetNotificationOutbox(
            client_id="client-1",
            event_type=FleetNotificationEventType.TEST.value,
            severity=FleetNotificationSeverity.LOW.value,
            event_ref_type="test",
            event_ref_id="00000000-0000-0000-0000-000000000000",
            payload_redacted={"hello": "world"},
            channels_attempted=[],
            status=FleetNotificationOutboxStatus.PENDING,
            attempts=0,
            next_attempt_at=_now(),
            dedupe_key="dedupe-1",
        )
        session.add_all([channel, policy, outbox])
        session.flush()

        dispatch_outbox_item(session, outbox_id=str(outbox.id))
        assert len(server.received) == 1
        first = server.received[0]
        ok, error = verify_webhook_signature(first["headers"], first["body"], "secret", now=int(time.time()))
        assert ok
        assert error is None

        outbox.next_attempt_at = _now()
        time.sleep(1)
        dispatch_outbox_item(session, outbox_id=str(outbox.id))
        assert len(server.received) == 2
        second = server.received[1]
        first_headers = {key.lower(): value for key, value in first["headers"].items()}
        second_headers = {key.lower(): value for key, value in second["headers"].items()}
        assert first_headers["x-neft-event-id"] == second_headers["x-neft-event-id"]
        assert first_headers["x-neft-nonce"] != second_headers["x-neft-nonce"]
        assert first_headers["x-neft-timestamp"] != second_headers["x-neft-timestamp"]
    finally:
        server.shutdown()
        _teardown(session)
