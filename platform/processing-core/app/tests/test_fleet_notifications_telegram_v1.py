from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.fuel import (
    FleetNotificationChannel,
    FleetNotificationChannelStatus,
    FleetNotificationChannelType,
    FleetNotificationEventType,
    FleetNotificationPolicy,
    FleetNotificationPolicyScopeType,
    FleetNotificationSeverity,
    FleetTelegramBinding,
    FleetTelegramBindingScopeType,
    FleetTelegramBindingStatus,
    FleetTelegramChatType,
    FuelCard,
    FuelCardStatus,
    FuelLimitBreach,
    FuelLimitBreachScopeType,
    FuelLimitBreachStatus,
    FuelLimitBreachType,
    FuelLimitPeriod,
)
from app.services.fleet_notification_dispatcher import dispatch_outbox_item, enqueue_breach_notification
from app.services.notifications.telegram_sender import TelegramSendResult
from app.tests._fuel_runtime_test_harness import (
    FLEET_NOTIFICATION_TELEGRAM_TEST_TABLES,
    fuel_runtime_session_context,
)


@pytest.fixture()
def db_session():
    with fuel_runtime_session_context(tables=FLEET_NOTIFICATION_TELEGRAM_TEST_TABLES) as session:
        yield session


def test_breach_dispatches_telegram_notification(monkeypatch, db_session) -> None:
    monkeypatch.setattr("app.services.fleet_notification_dispatcher.fleet_service._emit_event", lambda *args, **kwargs: str(uuid4()))
    client_id = str(uuid4())
    card = FuelCard(
        tenant_id=1,
        client_id=client_id,
        card_token="tok-1",
        card_alias="NEFT-000123",
        status=FuelCardStatus.ACTIVE,
    )
    db_session.add(card)
    db_session.flush()

    breach = FuelLimitBreach(
        client_id=client_id,
        scope_type=FuelLimitBreachScopeType.CARD,
        scope_id=card.id,
        period=FuelLimitPeriod.DAILY,
        limit_id=str(uuid4()),
        breach_type=FuelLimitBreachType.AMOUNT,
        threshold=1000,
        observed=1500,
        delta=500,
        occurred_at=datetime.now(timezone.utc),
        status=FuelLimitBreachStatus.OPEN,
    )
    db_session.add(breach)

    binding = FleetTelegramBinding(
        client_id=client_id,
        scope_type=FleetTelegramBindingScopeType.CLIENT,
        scope_id=None,
        chat_id=101,
        chat_title="Fleet Ops",
        chat_type=FleetTelegramChatType.GROUP,
        status=FleetTelegramBindingStatus.ACTIVE,
        verified_at=datetime.now(timezone.utc),
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

    policy = FleetNotificationPolicy(
        client_id=client_id,
        scope_type=FleetNotificationPolicyScopeType.CLIENT,
        scope_id=None,
        event_type=FleetNotificationEventType.LIMIT_BREACH,
        severity_min=FleetNotificationSeverity.LOW,
        channels=[FleetNotificationChannelType.TELEGRAM.value],
        cooldown_seconds=60,
        active=True,
    )
    db_session.add(policy)
    db_session.commit()

    outbox = enqueue_breach_notification(
        db_session,
        breach=breach,
        principal=None,
        request_id=None,
        trace_id=None,
    )

    sent = {}

    def _send_message(chat_id: int, text: str, **kwargs):
        sent["chat_id"] = chat_id
        sent["text"] = text
        return TelegramSendResult(status_code=200, body="ok", message_id="1")

    monkeypatch.setattr("app.services.fleet_notification_dispatcher.send_message", _send_message)

    outbox = dispatch_outbox_item(db_session, outbox_id=str(outbox.id))

    assert outbox.status.value == "SENT"
    assert sent["chat_id"] == 101
    assert "LIMIT_BREACH" in sent["text"]
