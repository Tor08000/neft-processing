from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from neft_integration_hub.db import Base
from neft_integration_hub.schemas import WebhookOwner
from neft_integration_hub.services.webhooks import (
    build_event_envelope,
    create_endpoint,
    decrypt_secret,
    encrypt_secret,
    enqueue_delivery,
)


def _make_sqlite_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def test_build_event_envelope_contract():
    event_id = str(uuid4())
    envelope = build_event_envelope(
        event_id=event_id,
        event_type="logistics.route.updated",
        correlation_id="corr-1",
        owner=WebhookOwner(type="CLIENT", id="client-1"),
        payload={"status": "OK"},
        schema_version=1,
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    assert envelope.event_id == event_id
    assert envelope.event_type == "logistics.route.updated"
    assert envelope.schema_version == 1
    assert envelope.correlation_id == "corr-1"
    assert envelope.owner.type == "CLIENT"
    assert envelope.owner.id == "client-1"
    assert envelope.payload == {"status": "OK"}


def test_secret_encrypt_roundtrip():
    secret = "super-secret"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    assert decrypt_secret(encrypted) == secret


def test_enqueue_delivery_deduplicates():
    db = _make_sqlite_session()
    endpoint, _secret = create_endpoint(db, owner_type="CLIENT", owner_id="client-1", url="https://example.com")
    envelope = build_event_envelope(
        event_id="11111111-1111-1111-1111-111111111111",
        event_type="docs.ready",
        correlation_id="corr-2",
        owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
        payload={"doc_id": "doc-1"},
    )

    first = enqueue_delivery(db, endpoint=endpoint, envelope=envelope)
    second = enqueue_delivery(db, endpoint=endpoint, envelope=envelope)

    assert first.id == second.id
