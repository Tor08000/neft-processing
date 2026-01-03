from __future__ import annotations

import os

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
)
from app.services.fleet_notification_dispatcher import _now, dispatch_outbox_item
from app.services.notifications.stub_sender import STATUS_ACCEPTED, STATUS_FAILED, process_stub_delivery_outcomes


def _make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    FleetNotificationChannel.__table__.create(bind=engine)
    FleetNotificationPolicy.__table__.create(bind=engine)
    FleetNotificationOutbox.__table__.create(bind=engine)
    NotificationDeliveryLog.__table__.create(bind=engine)
    session = SessionLocal()
    session._engine = engine
    return session


def _teardown(session: Session) -> None:
    engine = session._engine
    session.close()
    NotificationDeliveryLog.__table__.drop(bind=engine)
    FleetNotificationOutbox.__table__.drop(bind=engine)
    FleetNotificationPolicy.__table__.drop(bind=engine)
    FleetNotificationChannel.__table__.drop(bind=engine)
    engine.dispose()


def test_sms_stub_creates_accept_log() -> None:
    os.environ["SMS_STUB_DELIVERY_DELAY_MS"] = "60000"
    os.environ["SMS_STUB_FAIL_RATE"] = "0"
    session = _make_session()
    try:
        channel = FleetNotificationChannel(
            client_id="client-1",
            channel_type=FleetNotificationChannelType.SMS,
            target="+10000000000",
            status=FleetNotificationChannelStatus.ACTIVE,
            secret_ref=None,
        )
        policy = FleetNotificationPolicy(
            client_id="client-1",
            scope_type=FleetNotificationPolicyScopeType.CLIENT,
            scope_id=None,
            event_type=FleetNotificationEventType.TEST,
            severity_min=FleetNotificationSeverity.LOW,
            channels=[FleetNotificationChannelType.SMS.value],
            cooldown_seconds=300,
            active=True,
        )
        outbox = FleetNotificationOutbox(
            client_id="client-1",
            event_type=FleetNotificationEventType.TEST.value,
            severity=FleetNotificationSeverity.LOW.value,
            event_ref_type="test",
            event_ref_id="00000000-0000-0000-0000-000000000000",
            payload_redacted={"message": "hello"},
            channels_attempted=[],
            status=FleetNotificationOutboxStatus.PENDING,
            attempts=0,
            next_attempt_at=_now(),
            dedupe_key="dedupe-sms",
        )
        session.add_all([channel, policy, outbox])
        session.flush()

        dispatch_outbox_item(session, outbox_id=str(outbox.id))
        log = session.query(NotificationDeliveryLog).one()
        assert log.status == STATUS_ACCEPTED
    finally:
        _teardown(session)


def test_sms_stub_updates_delivery_status() -> None:
    os.environ["SMS_STUB_DELIVERY_DELAY_MS"] = "0"
    os.environ["SMS_STUB_FAIL_RATE"] = "1"
    session = _make_session()
    try:
        channel = FleetNotificationChannel(
            client_id="client-1",
            channel_type=FleetNotificationChannelType.SMS,
            target="+10000000000",
            status=FleetNotificationChannelStatus.ACTIVE,
            secret_ref=None,
        )
        policy = FleetNotificationPolicy(
            client_id="client-1",
            scope_type=FleetNotificationPolicyScopeType.CLIENT,
            scope_id=None,
            event_type=FleetNotificationEventType.TEST,
            severity_min=FleetNotificationSeverity.LOW,
            channels=[FleetNotificationChannelType.SMS.value],
            cooldown_seconds=300,
            active=True,
        )
        outbox = FleetNotificationOutbox(
            client_id="client-1",
            event_type=FleetNotificationEventType.TEST.value,
            severity=FleetNotificationSeverity.LOW.value,
            event_ref_type="test",
            event_ref_id="00000000-0000-0000-0000-000000000000",
            payload_redacted={"message": "hello"},
            channels_attempted=[],
            status=FleetNotificationOutboxStatus.PENDING,
            attempts=0,
            next_attempt_at=_now(),
            dedupe_key="dedupe-sms",
        )
        session.add_all([channel, policy, outbox])
        session.flush()

        dispatch_outbox_item(session, outbox_id=str(outbox.id))
        process_stub_delivery_outcomes(
            session,
            provider="sms_stub",
            channel=FleetNotificationChannelType.SMS.value,
            delay_ms=0,
            fail_rate=1.0,
        )
        log = session.query(NotificationDeliveryLog).one()
        assert log.status == STATUS_FAILED
    finally:
        _teardown(session)
