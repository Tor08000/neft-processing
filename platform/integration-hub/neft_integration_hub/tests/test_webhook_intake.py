from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("neft_integration_hub")

import neft_integration_hub.main as main_module
from neft_integration_hub.services.webhook_intake import compute_signature, record_intake_event, verify_signature
from neft_integration_hub.tests._db import WEBHOOK_INTAKE_TABLES, make_sqlite_session, make_sqlite_session_factory


def _make_sqlite_session():
    return make_sqlite_session(*WEBHOOK_INTAKE_TABLES)


def test_signature_verification_and_recording():
    db = _make_sqlite_session()
    payload = b'{"event_type":"test","payload":{"foo":"bar"}}'
    secret = "secret"
    signature = compute_signature(payload, secret)

    verified, header = verify_signature(payload, f"sha256={signature}", secret)
    assert verified is True

    event = record_intake_event(
        db,
        source="client",
        event_type="test.event",
        payload={"foo": "bar"},
        event_id="evt-1",
        signature=header,
        verified=verified,
        request_id="req-1",
        trace_id="trace-1",
    )

    assert event.record.source == "client"
    assert event.record.event_type == "test.event"
    assert event.record.signature == header
    assert event.record.verified is True
    assert event.duplicate is False


def test_record_intake_event_marks_duplicate_by_source_and_event_id():
    db = _make_sqlite_session()
    first = record_intake_event(
        db,
        source="client",
        event_type="test.event",
        payload={"foo": "bar"},
        event_id="evt-dup",
        signature="sha256=test",
        verified=True,
        request_id="req-1",
        trace_id="trace-1",
    )
    second = record_intake_event(
        db,
        source="client",
        event_type="test.event",
        payload={"foo": "bar"},
        event_id="evt-dup",
        signature="sha256=test",
        verified=True,
        request_id="req-2",
        trace_id="trace-2",
    )

    assert first.duplicate is False
    assert second.duplicate is True
    assert first.record.id == second.record.id


@pytest.fixture()
def webhook_api_client():
    testing_session_local = make_sqlite_session_factory(*WEBHOOK_INTAKE_TABLES, static_pool=True)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_get_db
    object.__setattr__(main_module.settings, "webhook_allow_unsigned", False)
    try:
        with TestClient(main_module.app) as client:
            yield client
    finally:
        main_module.app.dependency_overrides.clear()


def test_webhook_intake_requires_signature_by_default(webhook_api_client):
    response = webhook_api_client.post(
        "/v1/webhooks/client/events",
        json={"event_type": "test.event", "payload": {"foo": "bar"}, "event_id": "evt-no-sig"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "signature_required"


def test_webhook_intake_returns_duplicate_status(webhook_api_client):
    payload = {"event_type": "test.event", "payload": {"foo": "bar"}, "event_id": "evt-dup-api"}
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = compute_signature(raw_payload, "change-me")

    first = webhook_api_client.post(
        "/v1/webhooks/client/events",
        content=raw_payload,
        headers={"X-Webhook-Signature": f"sha256={signature}", "Content-Type": "application/json"},
    )
    second = webhook_api_client.post(
        "/v1/webhooks/client/events",
        content=raw_payload,
        headers={"X-Webhook-Signature": f"sha256={signature}", "Content-Type": "application/json"},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert first.json()["duplicate"] is False
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["duplicate"] is True
