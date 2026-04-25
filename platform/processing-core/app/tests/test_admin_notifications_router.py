from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.notifications import NotificationChannel, NotificationTemplate
from app.routers.admin.notifications import create_notification_template
from app.schemas.notifications import NotificationTemplateIn


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[NotificationTemplate.__table__])
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def test_create_notification_template_returns_conflict_for_duplicate_code(db_session) -> None:
    payload = NotificationTemplateIn(
        code="webhook_test",
        event_type="WEBHOOK_TEST",
        channel=NotificationChannel.WEBHOOK,
        body="Webhook payload {event}",
    )

    created = create_notification_template(payload=payload, db=db_session)

    assert created.code == "webhook_test"

    with pytest.raises(HTTPException) as excinfo:
        create_notification_template(payload=payload, db=db_session)

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "notification_template_code_conflict"
