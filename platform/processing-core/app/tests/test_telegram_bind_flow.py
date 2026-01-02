from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.models.fuel import (
    FleetNotificationChannel,
    FleetNotificationChannelType,
    FleetTelegramBindingScopeType,
    FleetTelegramBindingStatus,
    FleetTelegramChatType,
)
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.fleet_notification_dispatcher import _now


def _principal(client_id: str) -> Principal:
    return Principal(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        roles={"client_admin"},
        scopes=set(),
        client_id=UUID(client_id),
        partner_id=None,
        is_admin=False,
        raw_claims={"tenant_id": 1},
    )


def test_telegram_bind_flow_issues_and_uses_token(db_session) -> None:
    client_id = str(uuid4())
    principal = _principal(client_id)

    token = fleet_service.issue_telegram_link_token(
        db_session,
        client_id=client_id,
        scope_type=FleetTelegramBindingScopeType.CLIENT,
        scope_id=None,
        principal=principal,
        request_id=None,
        trace_id=None,
    )

    binding = fleet_service.bind_telegram_chat(
        db_session,
        token_value=token.token,
        chat_id=12345,
        chat_title="Fleet Alerts",
        chat_type=FleetTelegramChatType.GROUP,
    )
    db_session.commit()

    channel = (
        db_session.query(FleetNotificationChannel)
        .filter(FleetNotificationChannel.client_id == client_id)
        .filter(FleetNotificationChannel.channel_type == FleetNotificationChannelType.TELEGRAM)
        .one_or_none()
    )

    assert binding.status == FleetTelegramBindingStatus.ACTIVE
    assert binding.verified_at is not None
    assert channel is not None
    assert channel.target == f"telegram:{binding.id}"

    with pytest.raises(HTTPException) as excinfo:
        fleet_service.bind_telegram_chat(
            db_session,
            token_value=token.token,
            chat_id=12345,
            chat_title="Fleet Alerts",
            chat_type=FleetTelegramChatType.GROUP,
        )
    assert excinfo.value.status_code == 409


def test_telegram_bind_flow_rejects_expired_token(db_session) -> None:
    client_id = str(uuid4())
    principal = _principal(client_id)
    token = fleet_service.issue_telegram_link_token(
        db_session,
        client_id=client_id,
        scope_type=FleetTelegramBindingScopeType.CLIENT,
        scope_id=None,
        principal=principal,
        request_id=None,
        trace_id=None,
    )
    token.expires_at = _now() - timedelta(minutes=1)

    with pytest.raises(HTTPException) as excinfo:
        fleet_service.bind_telegram_chat(
            db_session,
            token_value=token.token,
            chat_id=222,
            chat_title="Expired",
            chat_type=FleetTelegramChatType.PRIVATE,
        )
    assert excinfo.value.status_code == 410
