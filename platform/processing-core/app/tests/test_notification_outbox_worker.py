from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.notification_outbox import NotificationOutbox
from app.services.client_invitation_notifications import process_notification_outbox


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def test_outbox_new_to_sent(db_session, monkeypatch):
    db_session.add(
        NotificationOutbox(
            event_type="client_invitation_resent",
            aggregate_type="client_invitation",
            aggregate_id="inv-1",
            payload={"channel": "email", "to": "u@example.com"},
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
    db_session.add(
        NotificationOutbox(
            event_type="client_invitation_resent",
            aggregate_type="client_invitation",
            aggregate_id="inv-2",
            payload={"channel": "email", "to": "u@example.com"},
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
