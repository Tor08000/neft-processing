from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timezone
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient
from neft_shared.settings import get_settings

import app.main as app_main
from app.db import Base, engine, get_sessionmaker
from app.db.types import new_uuid_str
from app.main import app
from app.models.audit_log import AuditLog
from app.models.edo import (
    EdoAccount,
    EdoCounterparty,
    EdoCounterpartySubjectType,
    EdoDocument,
    EdoDocumentKind,
    EdoDocumentStatus,
    EdoInboundEvent,
    EdoOutbox,
    EdoOutboxStatus,
    EdoProvider,
    EdoSubjectType,
    EdoTransition,
)
from app.integrations.edo.dtos import EdoSendResult
from app.services.edo import EdoService


TEST_TABLES = [
    AuditLog.__table__,
    EdoAccount.__table__,
    EdoCounterparty.__table__,
    EdoDocument.__table__,
    EdoTransition.__table__,
    EdoInboundEvent.__table__,
    EdoOutbox.__table__,
]


@pytest.fixture(autouse=True)
def clean_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
    Base.metadata.drop_all(bind=engine, tables=TEST_TABLES)
    Base.metadata.create_all(bind=engine, tables=TEST_TABLES)
    yield
    Base.metadata.drop_all(bind=engine, tables=TEST_TABLES)


def test_sbis_webhook_signature_updates_document() -> None:
    session = get_sessionmaker()()
    account_id = new_uuid_str()
    secret = "test-secret"
    os.environ["SBIS_TEST_WEBHOOK_SECRET"] = secret
    os.environ["SBIS_TEST_CREDENTIALS"] = json.dumps({"base_url": "http://sbis.test"})
    try:
        account = EdoAccount(
            id=account_id,
            provider=EdoProvider.SBIS,
            name="Test SBIS",
            box_id="box-1",
            credentials_ref="env:SBIS_TEST_CREDENTIALS",
            webhook_secret_ref="env:SBIS_TEST_WEBHOOK_SECRET",
            is_active=True,
        )
        session.add(account)
        counterparty_id = new_uuid_str()
        counterparty = EdoCounterparty(
            id=counterparty_id,
            provider=EdoProvider.SBIS,
            subject_type=EdoCounterpartySubjectType.CLIENT,
            subject_id="client-1",
            provider_counterparty_id="provider-counterparty-1",
        )
        session.add(counterparty)
        doc = EdoDocument(
            id=new_uuid_str(),
            provider=EdoProvider.SBIS,
            account_id=account_id,
            subject_type=EdoSubjectType.CLIENT,
            subject_id="client-1",
            document_registry_id=new_uuid_str(),
            document_kind=EdoDocumentKind.INVOICE,
            provider_doc_id="doc-123",
            status=EdoDocumentStatus.DELIVERED,
            counterparty_id=counterparty_id,
            send_dedupe_key="dedupe-1",
        )
        session.add(doc)
        session.commit()

        payload = {
            "event_id": "evt-1",
            "provider_doc_id": "doc-123",
            "status": "SIGNED",
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), payload_bytes, sha256).hexdigest()
        signature_header = get_settings().EDO_WEBHOOK_SIGNATURE_HEADER
        with TestClient(app) as client:
            response = client.post(
                "/integrations/edo/sbis/webhook",
                headers={
                    signature_header: signature,
                    "x-edo-account-id": account_id,
                    "content-type": "application/json",
                },
                content=payload_bytes,
            )
        assert response.status_code == 200
    finally:
        session.close()


def test_edo_outbox_dispatch_uses_payload_document_id(monkeypatch: pytest.MonkeyPatch) -> None:
    session = get_sessionmaker()()
    account_id = new_uuid_str()
    counterparty_id = new_uuid_str()
    document_id = new_uuid_str()
    outbox_id = new_uuid_str()
    assert outbox_id != document_id

    account = EdoAccount(
        id=account_id,
        provider=EdoProvider.SBIS,
        name="Test SBIS",
        box_id="box-1",
        credentials_ref="env:SBIS_TEST_CREDENTIALS",
        webhook_secret_ref="env:SBIS_TEST_WEBHOOK_SECRET",
        is_active=True,
    )
    counterparty = EdoCounterparty(
        id=counterparty_id,
        provider=EdoProvider.SBIS,
        subject_type=EdoCounterpartySubjectType.PARTNER,
        subject_id="partner-1",
        provider_counterparty_id="provider-counterparty-1",
    )
    document = EdoDocument(
        id=document_id,
        provider=EdoProvider.SBIS,
        account_id=account_id,
        subject_type=EdoSubjectType.PARTNER,
        subject_id="partner-1",
        document_registry_id=new_uuid_str(),
        document_kind=EdoDocumentKind.ACT,
        status=EdoDocumentStatus.DRAFT,
        counterparty_id=counterparty_id,
        send_dedupe_key="send-1",
    )
    outbox = EdoOutbox(
        id=outbox_id,
        event_type="EDO_SEND_REQUESTED",
        payload={
            "edo_document_id": document_id,
            "account_id": account_id,
            "document_registry_id": str(document.document_registry_id),
            "counterparty_id": counterparty_id,
            "doc_type": document.document_kind.value,
            "meta": {"source": "test"},
        },
        dedupe_key="send-1",
        status=EdoOutboxStatus.PENDING,
    )
    session.add_all([account, counterparty, document, outbox])
    session.commit()

    seen: dict[str, str] = {}

    def fake_send(self: EdoService, request) -> EdoSendResult:
        seen["edo_document_id"] = request.edo_document_id
        record = self.db.get(EdoDocument, request.edo_document_id)
        record.provider_doc_id = "provider-doc-1"
        record.status = EdoDocumentStatus.SENT
        return EdoSendResult(
            provider_doc_id="provider-doc-1",
            provider_message_id=None,
            status=EdoDocumentStatus.SENT,
            raw={"provider_doc_id": "provider-doc-1"},
        )

    monkeypatch.setattr(EdoService, "send", fake_send)

    try:
        dispatched = EdoService(session).dispatch_outbox_item(outbox)
        session.flush()

        assert seen["edo_document_id"] == document_id
        assert dispatched.status == EdoOutboxStatus.SENT
        assert dispatched.last_error is None
    finally:
        session.close()
