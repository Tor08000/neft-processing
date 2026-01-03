from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from neft_integration_hub.db import Base
from neft_integration_hub.services.webhook_intake import compute_signature, record_intake_event, verify_signature


def _make_sqlite_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


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

    assert event.source == "client"
    assert event.event_type == "test.event"
    assert event.signature == header
    assert event.verified is True
