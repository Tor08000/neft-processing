from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import sys

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("neft_integration_hub")


try:
    import prometheus_client  # noqa: F401
except ModuleNotFoundError:
    class _MetricStub:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            return None

        def set(self, *args, **kwargs):
            return None

        def observe(self, *args, **kwargs):
            return None

    sys.modules["prometheus_client"] = SimpleNamespace(
        CONTENT_TYPE_LATEST="text/plain",
        Counter=_MetricStub,
        Gauge=_MetricStub,
        Histogram=_MetricStub,
        generate_latest=lambda: b"",
    )

from neft_integration_hub import main as main_module
from neft_integration_hub.db import Base
from neft_integration_hub.schemas import WebhookOwner
from neft_integration_hub.models import WebhookDelivery, WebhookDeliveryStatus
from neft_integration_hub.services.webhooks import (
    build_event_envelope,
    compute_sla,
    create_endpoint,
    create_subscription,
    decrypt_secret,
    encrypt_secret,
    enqueue_delivery,
    evaluate_alerts,
    pause_endpoint,
    resume_endpoint,
    schedule_replay,
)
from neft_integration_hub.settings import get_settings
from neft_integration_hub.tests._db import WEBHOOK_TABLES, make_sqlite_session, make_sqlite_session_factory


def _make_sqlite_session():
    return make_sqlite_session(*WEBHOOK_TABLES)


@pytest.fixture()
def webhook_api_client(monkeypatch: pytest.MonkeyPatch):
    testing_session_local = make_sqlite_session_factory(*WEBHOOK_TABLES, static_pool=True)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setattr(main_module.celery_app, "send_task", lambda *args, **kwargs: None)
    main_module.app.dependency_overrides[main_module.get_db] = override_get_db
    try:
        with TestClient(main_module.app) as client:
            yield client, testing_session_local
    finally:
        main_module.app.dependency_overrides.pop(main_module.get_db, None)


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
    db.expire_all()
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
            occurred_at=now,
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
            occurred_at=now,
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
            occurred_at=now,
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


def test_webhook_endpoint_and_subscription_routes(webhook_api_client):
    client, session_factory = webhook_api_client
    with session_factory() as db:
        endpoint, _secret = create_endpoint(db, owner_type="PARTNER", owner_id="partner-1", url="https://partner.example.com/webhooks")
        subscription = create_subscription(
            db,
            endpoint_id=endpoint.id,
            event_type="orders.updated",
            schema_version=1,
            filters={"station_id": "station-1"},
            enabled=True,
        )
        endpoint_id = endpoint.id
        subscription_id = subscription.id

    response = client.get("/v1/webhooks/subscriptions", params={"endpoint_id": endpoint_id})
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": subscription_id,
            "endpoint_id": endpoint_id,
            "event_type": "orders.updated",
            "schema_version": 1,
            "filters": {"station_id": "station-1"},
            "enabled": True,
        }
    ]

    response = client.patch(
        f"/v1/webhooks/endpoints/{endpoint_id}",
        json={"status": "DISABLED", "url": "https://partner.example.com/updated"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    assert response.json()["url"] == "https://partner.example.com/updated"

    response = client.patch(f"/v1/webhooks/subscriptions/{subscription_id}", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    response = client.delete(f"/v1/webhooks/subscriptions/{subscription_id}")
    assert response.status_code == 204

    response = client.get("/v1/webhooks/subscriptions", params={"endpoint_id": endpoint_id})
    assert response.status_code == 200
    assert response.json() == []


def test_webhook_delivery_routes_support_ui_filters_detail_and_retry(webhook_api_client):
    client, session_factory = webhook_api_client
    with session_factory() as db:
        endpoint, _secret = create_endpoint(db, owner_type="PARTNER", owner_id="partner-1", url="https://partner.example.com/webhooks")
        matching = enqueue_delivery(
            db,
            endpoint=endpoint,
            envelope=build_event_envelope(
                event_id="99999999-9999-9999-9999-999999999991",
                event_type="orders.updated",
                correlation_id="corr-delivery-1",
                owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
                payload={"order_id": "order-1"},
                occurred_at=datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc),
            ),
        )
        matching.status = WebhookDeliveryStatus.FAILED.value
        matching.attempt = 2
        matching.last_http_status = 502
        matching.last_error = "upstream_timeout"
        matching.next_retry_at = None
        db.add(matching)

        other = enqueue_delivery(
            db,
            endpoint=endpoint,
            envelope=build_event_envelope(
                event_id="99999999-9999-9999-9999-999999999992",
                event_type="catalog.updated",
                correlation_id="corr-delivery-2",
                owner=WebhookOwner(type=endpoint.owner_type, id=endpoint.owner_id),
                payload={"catalog_id": "catalog-1"},
                occurred_at=datetime(2024, 1, 3, 12, 0, tzinfo=timezone.utc),
            ),
        )
        other.status = WebhookDeliveryStatus.DELIVERED.value
        db.add(other)
        db.commit()
        delivery_id = matching.id
        endpoint_id = endpoint.id
        event_id = matching.event_id

    response = client.get(
        "/v1/webhooks/deliveries",
        params={
            "endpoint_id": endpoint_id,
            "status": "FAILED",
            "from": "2024-01-02",
            "to": "2024-01-02",
            "limit": 20,
            "event_type": "orders.updated",
            "event_id": event_id,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == delivery_id

    response = client.get(f"/v1/webhooks/deliveries/{delivery_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["endpoint_url"] == "https://partner.example.com/webhooks"
    assert detail["correlation_id"] == "corr-delivery-1"
    assert detail["envelope"]["payload"] == {"order_id": "order-1"}
    assert detail["headers"]["X-NEFT-Event-Id"] == event_id
    assert detail["attempts"] == [
        {
            "attempt": 2,
            "http_status": 502,
            "error": "upstream_timeout",
            "latency_ms": None,
            "delivered_at": None,
            "next_retry_at": None,
            "correlation_id": "corr-delivery-1",
        }
    ]

    with patch.object(main_module.celery_app, "send_task") as send_task_mock:
        response = client.post(f"/v1/webhooks/deliveries/{delivery_id}/retry")

    assert response.status_code == 200
    assert response.json() == {"delivery_id": delivery_id}
    send_task_mock.assert_called_once_with("webhook.deliver", args=[delivery_id])

    with session_factory() as db:
        refreshed = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
        assert refreshed is not None
        assert refreshed.status == WebhookDeliveryStatus.PENDING.value
        assert refreshed.next_retry_at is not None
        assert refreshed.last_http_status is None
        assert refreshed.last_error is None


def test_webhook_test_route_accepts_payload_contract(webhook_api_client):
    client, session_factory = webhook_api_client
    with session_factory() as db:
        endpoint, _secret = create_endpoint(db, owner_type="PARTNER", owner_id="partner-1", url="https://partner.example.com/webhooks")
        endpoint_id = endpoint.id

    with patch.object(main_module.celery_app, "send_task") as send_task_mock:
        response = client.post(
            f"/v1/webhooks/endpoints/{endpoint_id}/test",
            json={"event_type": "test.ping", "payload": {"hello": "world"}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_id"]
    assert body["status"] == WebhookDeliveryStatus.PENDING.value
    assert body["http_status"] is None
    assert body["latency_ms"] is None
    assert body["error"] is None
    send_task_mock.assert_called_once()

    with session_factory() as db:
        delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == body["delivery_id"]).first()
        assert delivery is not None
        assert delivery.event_type == "test.ping"
        assert delivery.payload["payload"] == {"hello": "world"}
