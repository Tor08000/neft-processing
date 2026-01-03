from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("neft_integration_hub")

from neft_integration_hub.db import Base
from neft_integration_hub.main import app
from neft_integration_hub.models import EdoDocumentStatus
from neft_integration_hub.schemas import DispatchRequest
from neft_integration_hub.services.edo_service import dispatch_request, poll_document, send_document


def _make_sqlite_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def test_dispatch_idempotent_creates_record():
    db = _make_sqlite_session()
    payload = DispatchRequest(
        document_id="11111111-1111-1111-1111-111111111111",
        signature_id="22222222-2222-2222-2222-222222222222",
        provider="DIADOK",
        artifact={"bucket": "bucket", "object_key": "object", "sha256": None},
        counterparty={"inn": "7700000000", "kpp": "770001001", "edo_id": None},
        idempotency_key="idem-1",
        meta={"doc_type": "CLOSING_PACKAGE"},
    )

    first = dispatch_request(db, payload)
    second = dispatch_request(db, payload)

    assert first.id == second.id
    assert first.status == EdoDocumentStatus.QUEUED.value


def test_poll_transitions_after_send(monkeypatch):
    db = _make_sqlite_session()
    payload = DispatchRequest(
        document_id="33333333-3333-3333-3333-333333333333",
        signature_id=None,
        provider="DIADOK",
        artifact={"bucket": "bucket", "object_key": "object", "sha256": None},
        counterparty={"inn": "7700000000", "kpp": "770001001", "edo_id": None},
        idempotency_key="idem-2",
        meta={},
    )

    record = dispatch_request(db, payload)

    def _fake_bytes(*_args, **_kwargs):
        return b"payload"

    monkeypatch.setattr("neft_integration_hub.services.edo_service._load_artifact_bytes", _fake_bytes)

    record = send_document(db, record.id)
    assert record.status == EdoDocumentStatus.SENT.value

    record = poll_document(db, record.id)
    assert record.status in {EdoDocumentStatus.SENT.value, EdoDocumentStatus.DELIVERED.value}
