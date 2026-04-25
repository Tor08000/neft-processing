from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.notification_outbox import NotificationOutbox
from app.models.notifications import NotificationPriority, NotificationSubjectType
from app.services.client_invitation_notifications import process_notification_outbox


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[NotificationOutbox.__table__])
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def test_outbox_new_to_sent(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER_MODE", "integration_hub")
    invitation_id = str(uuid4())
    db_session.add(
        NotificationOutbox(
            event_type="client_invitation_resent",
            subject_type=NotificationSubjectType.CLIENT,
            subject_id="client-1",
            aggregate_type="client_invitation",
            aggregate_id=invitation_id,
            template_code="client_invitation",
            payload={"channel": "email", "to": "u@example.com"},
            priority=NotificationPriority.NORMAL,
            dedupe_key=f"client_invitation:{invitation_id}:sent:1",
            status="NEW",
            next_attempt_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    class Resp:
        status_code = 200

    monkeypatch.setattr("app.services.client_invitation_notifications.requests.post", lambda *args, **kwargs: Resp())
    sent = process_notification_outbox(db_session)
    db_session.commit()
    assert sent == 1
    row = db_session.query(NotificationOutbox).one()
    assert row.status == "SENT"


def test_outbox_retry_on_error(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER_MODE", "integration_hub")
    invitation_id = str(uuid4())
    db_session.add(
        NotificationOutbox(
            event_type="client_invitation_resent",
            subject_type=NotificationSubjectType.CLIENT,
            subject_id="client-1",
            aggregate_type="client_invitation",
            aggregate_id=invitation_id,
            template_code="client_invitation",
            payload={"channel": "email", "to": "u@example.com"},
            priority=NotificationPriority.NORMAL,
            dedupe_key=f"client_invitation:{invitation_id}:retry:1",
            status="NEW",
            next_attempt_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    class Resp:
        status_code = 500

    monkeypatch.setattr("app.services.client_invitation_notifications.requests.post", lambda *args, **kwargs: Resp())
    sent = process_notification_outbox(db_session)
    db_session.commit()
    assert sent == 0
    row = db_session.query(NotificationOutbox).one()
    assert row.attempts == 1
    assert row.status == "NEW"
    assert row.next_attempt_at is not None
