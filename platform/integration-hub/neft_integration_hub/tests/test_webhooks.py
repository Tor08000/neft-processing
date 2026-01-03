from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("neft_integration_hub")

from neft_integration_hub.db import Base
from neft_integration_hub.schemas import WebhookOwner
from neft_integration_hub.models import WebhookDelivery, WebhookDeliveryStatus
from neft_integration_hub.services.webhooks import (
    build_event_envelope,
    compute_sla,
    create_endpoint,
    decrypt_secret,
    encrypt_secret,
    enqueue_delivery,
    evaluate_alerts,
    pause_endpoint,
    resume_endpoint,
    schedule_replay,
)
from neft_integration_hub.settings import get_settings


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


def test_replay_creates_new_delivery_attempts():
    db = _make_sqlite_session()
    endpoint, _secret = create_endpoint(db, owner_type="CLIENT", owner_id="client-1", url="https://example.com")
    envelope = build_event_envelope(
        event_id="22222222-2222-2222-2222-222222222222",
        event_type="docs.ready",
        correlation_id="corr-3",
        owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
        payload={"doc_id": "doc-2"},
        occurred_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    delivery = enqueue_delivery(db, endpoint=endpoint, envelope=envelope)
    delivery.status = WebhookDeliveryStatus.FAILED.value
    db.add(delivery)
    db.commit()

    replay, scheduled = schedule_replay(
        db,
        endpoint=endpoint,
        from_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
        event_types=["docs.ready"],
        only_failed=True,
        created_by="client-1",
    )

    deliveries = db.query(WebhookDelivery).all()
    assert replay.id is not None
    assert scheduled == 1
    assert len(deliveries) == 2
    assert any(item.replay_id == replay.id for item in deliveries)


def test_pause_blocks_delivery_and_resume_restores():
    db = _make_sqlite_session()
    endpoint, _secret = create_endpoint(db, owner_type="CLIENT", owner_id="client-1", url="https://example.com")
    pause_endpoint(db, endpoint, "maintenance")
    envelope = build_event_envelope(
        event_id="33333333-3333-3333-3333-333333333333",
        event_type="docs.ready",
        correlation_id="corr-4",
        owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
        payload={"doc_id": "doc-3"},
    )
    delivery = enqueue_delivery(db, endpoint=endpoint, envelope=envelope)
    assert delivery.status == WebhookDeliveryStatus.PAUSED.value
    assert delivery.next_retry_at is None

    endpoint = resume_endpoint(db, endpoint)
    updated = db.query(WebhookDelivery).filter_by(id=delivery.id).first()
    assert endpoint.delivery_paused is False
    assert updated.status == WebhookDeliveryStatus.PENDING.value
    assert updated.next_retry_at is not None


def test_sla_calculation():
    db = _make_sqlite_session()
    endpoint, _secret = create_endpoint(db, owner_type="CLIENT", owner_id="client-1", url="https://example.com")
    now = datetime.now(timezone.utc)
    ok_delivery = enqueue_delivery(
        db,
        endpoint=endpoint,
        envelope=build_event_envelope(
            event_id="44444444-4444-4444-4444-444444444444",
            event_type="docs.ready",
            correlation_id="corr-5",
            owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
            payload={"doc_id": "doc-4"},
            occurred_at=now.isoformat(),
        ),
    )
    ok_delivery.status = WebhookDeliveryStatus.DELIVERED.value
    ok_delivery.latency_ms = 1000
    bad_delivery = enqueue_delivery(
        db,
        endpoint=endpoint,
        envelope=build_event_envelope(
            event_id="55555555-5555-5555-5555-555555555555",
            event_type="docs.ready",
            correlation_id="corr-6",
            owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
            payload={"doc_id": "doc-5"},
            occurred_at=now.isoformat(),
        ),
    )
    bad_delivery.status = WebhookDeliveryStatus.DELIVERED.value
    bad_delivery.latency_ms = 600000
    failed_delivery = enqueue_delivery(
        db,
        endpoint=endpoint,
        envelope=build_event_envelope(
            event_id="66666666-6666-6666-6666-666666666666",
            event_type="docs.ready",
            correlation_id="corr-7",
            owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
            payload={"doc_id": "doc-6"},
            occurred_at=now.isoformat(),
        ),
    )
    failed_delivery.status = WebhookDeliveryStatus.FAILED.value
    db.add_all([ok_delivery, bad_delivery, failed_delivery])
    db.commit()

    success_ratio, avg_latency_ms, breaches, total = compute_sla(db, endpoint=endpoint, window="5m")
    assert total == 3
    assert breaches == 1
    assert avg_latency_ms is not None
    assert success_ratio == 1 / 3


def test_alert_triggered_and_resolved():
    db = _make_sqlite_session()
    endpoint, _secret = create_endpoint(db, owner_type="CLIENT", owner_id="client-1", url="https://example.com")
    for idx in range(11):
        delivery = enqueue_delivery(
            db,
            endpoint=endpoint,
            envelope=build_event_envelope(
                event_id=f"77777777-7777-7777-7777-77777777777{idx}",
                event_type="docs.ready",
                correlation_id=f"corr-{idx}",
                owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
                payload={"doc_id": f"doc-{idx}"},
            ),
        )
        delivery.status = WebhookDeliveryStatus.FAILED.value
        db.add(delivery)
    db.commit()

    alerts = evaluate_alerts(db, endpoint=endpoint)
    assert any(alert.type == "DELIVERY_FAILURE" for alert in alerts)

    db.query(WebhookDelivery).update({WebhookDelivery.status: WebhookDeliveryStatus.DELIVERED.value})
    db.commit()
    alerts = evaluate_alerts(db, endpoint=endpoint)
    assert all(alert.type != "DELIVERY_FAILURE" for alert in alerts)


def test_alert_events_published():
    db = _make_sqlite_session()
    endpoint, _secret = create_endpoint(db, owner_type="CLIENT", owner_id="client-1", url="https://example.com")
    threshold = get_settings().webhook_alert_failure_threshold
    for idx in range(threshold + 1):
        delivery = enqueue_delivery(
            db,
            endpoint=endpoint,
            envelope=build_event_envelope(
                event_id=f"88888888-8888-8888-8888-88888888888{idx}",
                event_type="docs.ready",
                correlation_id=f"corr-8-{idx}",
                owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
                payload={"doc_id": f"doc-8-{idx}"},
            ),
        )
        delivery.status = WebhookDeliveryStatus.FAILED.value
        db.add(delivery)
    db.commit()

    with patch("neft_integration_hub.services.webhooks.publish_event") as publish_mock:
        evaluate_alerts(db, endpoint=endpoint)
        assert any(call.args[0].event_type == "WEBHOOK_ALERT_TRIGGERED" for call in publish_mock.call_args_list)

        db.query(WebhookDelivery).update({WebhookDelivery.status: WebhookDeliveryStatus.DELIVERED.value})
        db.commit()
        evaluate_alerts(db, endpoint=endpoint)
        assert any(call.args[0].event_type == "WEBHOOK_ALERT_RESOLVED" for call in publish_mock.call_args_list)
