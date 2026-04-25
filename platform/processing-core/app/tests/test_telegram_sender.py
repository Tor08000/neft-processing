from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from app.models.fuel import (
    FleetNotificationChannel,
    FleetNotificationChannelStatus,
    FleetNotificationChannelType,
    FleetNotificationEventType,
    FleetNotificationSeverity,
    FleetTelegramBinding,
    FleetTelegramBindingScopeType,
    FleetTelegramBindingStatus,
    FleetTelegramChatType,
)
from app.services.fleet_notification_dispatcher import dispatch_outbox_item, enqueue_notification, _now
from app.services.notifications.telegram_sender import TelegramSendError, TelegramSendResult
from app.tests._fuel_runtime_test_harness import (
    FLEET_NOTIFICATION_TELEGRAM_TEST_TABLES,
    fuel_runtime_session_context,
)


@pytest.fixture()
def db_session():
    with fuel_runtime_session_context(tables=FLEET_NOTIFICATION_TELEGRAM_TEST_TABLES) as session:
        yield session


@pytest.fixture(autouse=True)
def _suppress_case_event_emission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.fleet_notification_dispatcher.fleet_service._emit_event",
        lambda *args, **kwargs: str(uuid4()),
    )


def _create_binding(db_session, client_id: str) -> FleetTelegramBinding:
    binding = FleetTelegramBinding(
        client_id=client_id,
        scope_type=FleetTelegramBindingScopeType.CLIENT,
        scope_id=None,
        chat_id=1111,
        chat_title="Ops",
        chat_type=FleetTelegramChatType.GROUP,
        status=FleetTelegramBindingStatus.ACTIVE,
        verified_at=_now(),
    )
    db_session.add(binding)
    db_session.flush()
    channel = FleetNotificationChannel(
        client_id=client_id,
        channel_type=FleetNotificationChannelType.TELEGRAM,
        target=f"telegram:{binding.id}",
        status=FleetNotificationChannelStatus.ACTIVE,
    )
    db_session.add(channel)
    db_session.flush()
    return binding


def _create_outbox(db_session, client_id: str, event_ref_id: str):
    payload = {
        "client_id": client_id,
        "event_type": FleetNotificationEventType.TEST.value,
        "severity": FleetNotificationSeverity.HIGH.value,
        "summary": {"message": "Test"},
        "channels_override": [FleetNotificationChannelType.TELEGRAM.value],
        "route": "/client/fleet/notifications/alerts",
    }
    return enqueue_notification(
        db_session,
        client_id=client_id,
        event_type=FleetNotificationEventType.TEST,
        severity=FleetNotificationSeverity.HIGH,
        event_ref_type="test",
        event_ref_id=event_ref_id,
        payload=payload,
        principal=None,
        request_id=None,
        trace_id=None,
    )


def test_telegram_sender_sets_retry_after(monkeypatch, db_session) -> None:
    client_id = str(uuid4())
    _create_binding(db_session, client_id)
    outbox = _create_outbox(db_session, client_id, str(uuid4()))

    def _raise_rate_limit(*args, **kwargs):
        raise TelegramSendError("rate_limited", status_code=429, retry_after=30)

    monkeypatch.setattr("app.services.fleet_notification_dispatcher.send_message", _raise_rate_limit)

    before = _now()
    outbox = dispatch_outbox_item(db_session, outbox_id=str(outbox.id))

    assert outbox.status.value == "FAILED"
    assert outbox.next_attempt_at is not None
    assert outbox.next_attempt_at >= before + timedelta(seconds=30)


def test_telegram_sender_disables_binding_on_permanent_error(monkeypatch, db_session) -> None:
    client_id = str(uuid4())
    binding = _create_binding(db_session, client_id)
    outbox = _create_outbox(db_session, client_id, str(uuid4()))

    def _raise_permanent(*args, **kwargs):
        raise TelegramSendError("blocked", status_code=403, is_permanent=True)

    monkeypatch.setattr("app.services.fleet_notification_dispatcher.send_message", _raise_permanent)

    outbox = dispatch_outbox_item(db_session, outbox_id=str(outbox.id))
    channel = (
        db_session.query(FleetNotificationChannel)
        .filter(FleetNotificationChannel.target == f"telegram:{binding.id}")
        .one()
    )

    assert outbox.status.value in {"FAILED", "DEAD"}
    assert binding.status == FleetTelegramBindingStatus.DISABLED
    assert channel.status == FleetNotificationChannelStatus.DISABLED


def test_telegram_sender_records_dedupe_key(monkeypatch, db_session) -> None:
    client_id = str(uuid4())
    binding = _create_binding(db_session, client_id)
    outbox = _create_outbox(db_session, client_id, str(uuid4()))

    def _success(*args, **kwargs):
        return TelegramSendResult(status_code=200, body="ok", message_id="1")

    monkeypatch.setattr("app.services.fleet_notification_dispatcher.send_message", _success)

    outbox = dispatch_outbox_item(db_session, outbox_id=str(outbox.id))
    attempts = outbox.channels_attempted or []
    dedupe_keys = [entry.get("dedupe_key") for entry in attempts if isinstance(entry, dict)]

    assert f"client:{client_id}:evt:{outbox.event_ref_id}:tg:{binding.id}" in dedupe_keys
