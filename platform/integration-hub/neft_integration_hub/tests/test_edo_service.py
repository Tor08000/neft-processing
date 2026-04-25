from __future__ import annotations

import pytest

pytest.importorskip("neft_integration_hub")

from neft_integration_hub.models import EdoDocumentStatus
from neft_integration_hub.providers.base import ProviderStatus
from neft_integration_hub.schemas import DispatchRequest
from neft_integration_hub.services.edo_service import dispatch_request, poll_document, send_document
from neft_integration_hub.tests._db import EDO_TABLES, make_sqlite_session


def _make_sqlite_session():
    return make_sqlite_session(*EDO_TABLES)


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


def test_dispatch_rejects_conflicting_idempotency_key():
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

    dispatch_request(db, payload)
    payload.idempotency_key = "idem-2"

    with pytest.raises(ValueError, match="idempotency_conflict"):
        dispatch_request(db, payload)


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

    class _FakeProvider:
        def send(self, document_bytes: bytes, meta: dict) -> str:
            return "provider-message-1"

        def poll(self, provider_message_id: str) -> ProviderStatus:
            return ProviderStatus(status=EdoDocumentStatus.DELIVERED.value)

        def download_signed(self, provider_message_id: str):
            return None

    class _FakeRegistry:
        def get(self, provider: str):
            assert provider == "DIADOK"
            return _FakeProvider()

    monkeypatch.setattr("neft_integration_hub.services.edo_service._load_artifact_bytes", _fake_bytes)
    monkeypatch.setattr("neft_integration_hub.services.edo_service.get_registry", lambda: _FakeRegistry())

    record = send_document(db, record.id)
    assert record.status == EdoDocumentStatus.SENT.value

    record = poll_document(db, record.id)
    assert record.status == EdoDocumentStatus.DELIVERED.value
