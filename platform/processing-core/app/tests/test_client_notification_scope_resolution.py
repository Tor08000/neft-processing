from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.client import Client
from app.models.client_notification import ClientNotification
from app.services.client_notifications import (
    ClientNotificationSeverity,
    create_notification,
    resolve_client_email,
    resolve_client_scope_id,
)


def _engine():
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_resolve_client_scope_and_email_from_numeric_org_id_via_subscription() -> None:
    engine = _engine()
    metadata = MetaData()
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=True),
    )
    Client.__table__.create(bind=engine)
    metadata.create_all(bind=engine)

    client_id = "00000000-0000-0000-0000-000000000111"
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.add(Client(id=UUID(client_id), name="Acme Fuel", email="billing@acme.test", status="ACTIVE"))
        db.execute(
            client_subscriptions.insert().values(
                id="sub-101",
                tenant_id=101,
                client_id=client_id,
                created_at=now,
            )
        )
        db.commit()

        assert resolve_client_scope_id(db, "101") == client_id
        assert resolve_client_email(db, "101") == "billing@acme.test"


def test_create_notification_resolves_numeric_org_scope_before_insert() -> None:
    engine = _engine()
    metadata = MetaData()
    client_subscriptions = Table(
        "client_subscriptions",
        metadata,
        Column("id", String(64), primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("client_id", String(64), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=True),
    )
    Client.__table__.create(bind=engine)
    ClientNotification.__table__.create(bind=engine)
    metadata.create_all(bind=engine)

    client_id = "00000000-0000-0000-0000-000000000222"
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    with Session(bind=engine) as db:
        db.add(Client(id=UUID(client_id), name="Acme Fuel", email="ops@acme.test", status="ACTIVE"))
        db.execute(
            client_subscriptions.insert().values(
                id="sub-202",
                tenant_id=202,
                client_id=client_id,
                created_at=now,
            )
        )
        db.commit()

        notification = create_notification(
            db,
            org_id="202",
            event_type="payment_intake_submitted",
            severity=ClientNotificationSeverity.INFO,
            title="Оплата отправлена на проверку",
            body="Мы получили подтверждение оплаты.",
            entity_type="billing_payment_intake",
            entity_id="intake-1",
        )
        db.commit()

        assert notification is not None
        assert notification.org_id == client_id
        stored = db.query(ClientNotification).one()
        assert stored.org_id == client_id
        assert stored.entity_id == "intake-1"
